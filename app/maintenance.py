from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.openstack_client import openstack_client
import requests

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class DrainRequest(BaseModel):
    hypervisors: List[str] = Field(..., example=["openstack-controller", "openstack-compute01"], description="Drain edilecek hypervisor'lar")
    migration_order: Optional[str] = Field("smaller-first", example="smaller-first", description="Migration sırası: smaller-first veya bigger-first")
    max_concurrent_migration_per_hypervisor: Optional[int] = Field(1, example=2, description="Hypervisor başına eşzamanlı max migration sayısı")

class DrainResponse(BaseModel):
    message: str
    drained: List[str]
    migrations: Dict[str, int]
    vm_destinations: Dict[str, str]
    total_vms_migrated: int
    failed_migrations: List[str]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_server_hypervisor_mapping(conn):
    """Nova API'den direkt server-hypervisor mapping al"""
    try:
        nova_url = conn.compute.get_endpoint()
        token = conn.auth_token
        
        headers = {
            'X-Auth-Token': token,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{nova_url}/servers/detail?all_tenants=1",
            headers=headers,
            verify=False
        )
        
        if response.status_code != 200:
            return {}
        
        data = response.json()
        mapping = {}
        
        for server in data.get('servers', []):
            server_id = server.get('id')
            hypervisor_hostname = server.get('OS-EXT-SRV-ATTR:hypervisor_hostname')
            
            if server_id and hypervisor_hostname:
                mapping[server_id] = hypervisor_hostname
        
        return mapping
        
    except Exception as e:
        print(f"Error getting hypervisor mapping: {e}")
        return {}

def get_flavor_safe(conn, flavor_ref):
    """Flavor'ı ID veya name ile güvenli şekilde al"""
    try:
        # Önce ID olarak dene
        return conn.compute.get_flavor(flavor_ref)
    except:
        try:
            # Name olarak dene
            flavors = list(conn.compute.flavors())
            flavor = next((f for f in flavors if f.name == flavor_ref), None)
            if flavor:
                return flavor
        except:
            pass
        
        # Bulunamazsa default small flavor
        class DefaultFlavor:
            vcpus = 1
            ram = 2048
            disk = 20
            name = str(flavor_ref)
        return DefaultFlavor()

# ============================================================================
# MAINTENANCE ENDPOINTS
# ============================================================================

@router.post("/drain", response_model=DrainResponse, summary="Hypervisor'ları drain et (VM migration)")
async def drain_hypervisors(body: DrainRequest):
    """
    Belirtilen hypervisor'ları bakım moduna alır ve VM'leri diğer hypervisor'lara taşır.
    
    Migration algoritması:
    - smaller-first: Küçük VM'ler önce taşınır (daha hızlı)
    - bigger-first: Büyük VM'ler önce taşınır (kaynak önceliği)
    
    VM'ler mevcut kaynaklara göre en uygun hypervisor'a otomatik olarak yerleştirilir.
    """
    try:
        conn = openstack_client.get_connection()
        
        drained = []
        migrations: Dict[str, int] = {}
        vm_destinations: Dict[str, str] = {}
        failed_migrations: List[str] = []
        
        # Tüm hypervisor'ları ve VM'leri al
        all_hypervisors = list(conn.compute.hypervisors(details=True))
        all_servers = list(conn.compute.servers(details=True, all_tenants=True))
        
        # Server-Hypervisor mapping'i al
        server_hv_mapping = get_server_hypervisor_mapping(conn)
        
        # Drain edilecek hypervisor'ları bul
        hypervisors_to_drain = []
        for hv_name in body.hypervisors:
            hv = next((h for h in all_hypervisors if h.name == hv_name), None)
            if hv:
                hypervisors_to_drain.append(hv)
                drained.append(hv_name)
        
        if not hypervisors_to_drain:
            raise HTTPException(status_code=404, detail="Specified hypervisors not found")
        
        # Drain edilecek hypervisor'lardaki VM'leri topla
        vms_to_migrate = []
        for hv in hypervisors_to_drain:
            # Bu hypervisor'daki VM'leri bul
            hv_servers = []
            for s in all_servers:
                if server_hv_mapping.get(s.id) == hv.name:
                    hv_servers.append(s)
            
            for server in hv_servers:
                # Flavor bilgisini al - DÜZELTİLDİ
                flavor_id = server.flavor['id'] if isinstance(server.flavor, dict) else server.flavor.id
                flavor = get_flavor_safe(conn, flavor_id)
                
                vms_to_migrate.append({
                    'server': server,
                    'flavor': flavor,
                    'source_hypervisor': hv.name,
                    'size': flavor.vcpus + (flavor.ram / 1024) + (flavor.disk / 100)
                })
        
        if not vms_to_migrate:
            return DrainResponse(
                message="No VMs to migrate",
                drained=drained,
                migrations={},
                vm_destinations={},
                total_vms_migrated=0,
                failed_migrations=[]
            )
        
        # Migration sıralaması
        reverse_order = body.migration_order == "bigger-first"
        vms_to_migrate.sort(key=lambda x: x['size'], reverse=reverse_order)
        
        # Hedef hypervisor'ları hazırla
        target_hypervisors = [h for h in all_hypervisors if h.name not in body.hypervisors]
        
        if not target_hypervisors:
            raise HTTPException(status_code=400, detail="No available target hypervisors for migration")
        
        # VM'leri batch'ler halinde migrate et
        batch_size = body.max_concurrent_migration_per_hypervisor
        total_migrated = 0
        
        for i in range(0, len(vms_to_migrate), batch_size):
            batch = vms_to_migrate[i:i + batch_size]
            
            for vm_info in batch:
                server = vm_info['server']
                flavor = vm_info['flavor']
                source = vm_info['source_hypervisor']
                
                # En uygun hedef hypervisor'ı bul
                best_target = None
                min_usage = float('inf')
                
                for target_hv in target_hypervisors:
                    vcpus = getattr(target_hv, 'vcpus', 4) or 4
                    memory_size = getattr(target_hv, 'memory_mb', 16384) or 16384
                    vcpus_used = getattr(target_hv, 'vcpus_used', 0) or 0
                    memory_used = getattr(target_hv, 'memory_mb_used', 0) or 0
                    
                    cpu_usage = vcpus_used / vcpus if vcpus > 0 else 0
                    mem_usage = memory_used / memory_size if memory_size > 0 else 0
                    
                    if (vcpus_used + flavor.vcpus <= vcpus and
                        memory_used + flavor.ram <= memory_size):
                        
                        usage_score = cpu_usage + mem_usage
                        
                        if usage_score < min_usage:
                            min_usage = usage_score
                            best_target = target_hv
                
                if best_target:
                    try:
                        # Live migration başlat
                        conn.compute.live_migrate_server(
                            server.id,
                            host=best_target.name,
                            block_migration=False
                        )
                        
                        migrations[source] = migrations.get(source, 0) + 1
                        vm_destinations[server.id] = best_target.name
                        total_migrated += 1
                        
                        best_target.vcpus_used = getattr(best_target, 'vcpus_used', 0) + flavor.vcpus
                        best_target.memory_mb_used = getattr(best_target, 'memory_mb_used', 0) + flavor.ram
                        
                    except Exception as e:
                        failed_migrations.append(f"{server.name} ({server.id}): {str(e)}")
                else:
                    failed_migrations.append(f"{server.name} ({server.id}): No suitable target hypervisor found")
        
        message = f"Drain completed with '{body.migration_order}' order. Total VMs migrated: {total_migrated}"
        
        if failed_migrations:
            message += f". {len(failed_migrations)} migration(s) failed."
        
        return DrainResponse(
            message=message,
            drained=drained,
            migrations=migrations,
            vm_destinations=vm_destinations,
            total_vms_migrated=total_migrated,
            failed_migrations=failed_migrations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hypervisors/status", summary="Hypervisor durumlarını göster")
async def get_hypervisors_status():
    """Tüm hypervisor'ların durumunu gösterir"""
    try:
        conn = openstack_client.get_connection()
        
        hypervisors_list = list(conn.compute.hypervisors())
        all_servers = list(conn.compute.servers(details=True, all_tenants=True))
        
        # Server-Hypervisor mapping
        server_hv_mapping = get_server_hypervisor_mapping(conn)
        
        result = []
        for hv in hypervisors_list:
            hv_detail = conn.compute.get_hypervisor(hv.id)
            
            # Bu hypervisor'daki VM'leri say
            hv_vms = [s for s in all_servers if server_hv_mapping.get(s.id) == hv_detail.name]
            running_vms_count = len(hv_vms)
            
            # Kaynak bilgileri
            vcpus = getattr(hv_detail, 'vcpus', 0) or 4
            memory_size = getattr(hv_detail, 'memory_mb', 0) or 16384
            local_disk_size = getattr(hv_detail, 'local_gb', 0) or 100
            
            vcpus_used = 0
            memory_used = 0
            local_disk_used = 0
            
            # VM'lerden kullanılan kaynakları hesapla - DÜZELTİLDİ
            for vm in hv_vms:
                try:
                    flavor_id = vm.flavor.get('id') if isinstance(vm.flavor, dict) else vm.flavor.id
                    flavor = get_flavor_safe(conn, flavor_id)
                    
                    vcpus_used += flavor.vcpus
                    memory_used += flavor.ram
                    local_disk_used += flavor.disk
                except Exception as e:
                    print(f"Error getting flavor for {vm.name}: {e}")
                    pass
            
            cpu_usage_pct = (vcpus_used / vcpus * 100) if vcpus > 0 else 0
            memory_usage_pct = (memory_used / memory_size * 100) if memory_size > 0 else 0
            
            result.append({
                "hypervisor_name": hv_detail.name,
                "hypervisor_id": hv_detail.id,
                "status": getattr(hv_detail, 'status', 'unknown'),
                "state": getattr(hv_detail, 'state', 'unknown'),
                "running_vms": running_vms_count,
                "vcpus": {
                    "total": vcpus,
                    "used": vcpus_used,
                    "available": max(0, vcpus - vcpus_used),
                    "usage_percent": round(cpu_usage_pct, 2)
                },
                "memory_mb": {
                    "total": memory_size,
                    "used": memory_used,
                    "available": max(0, memory_size - memory_used),
                    "usage_percent": round(memory_usage_pct, 2)
                },
                "local_disk_gb": {
                    "total": local_disk_size,
                    "used": local_disk_used,
                    "available": max(0, local_disk_size - local_disk_used)
                }
            })
        
        return {
            "total_hypervisors": len(result),
            "hypervisors": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/vms", summary="VM attributes debug")
async def debug_vms():
    """VM-Hypervisor mapping'i göster"""
    try:
        conn = openstack_client.get_connection()
        mapping = get_server_hypervisor_mapping(conn)
        servers = list(conn.compute.servers(details=True, all_tenants=True))
        
        result = []
        for s in servers:
            result.append({
                "id": s.id,
                "name": s.name,
                "status": s.status,
                "hypervisor": mapping.get(s.id, "NOT_FOUND")
            })
        
        return {"servers": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))