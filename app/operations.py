from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.openstack_client import openstack_client

router = APIRouter(prefix="/api/operations", tags=["Operations"])

# ============================================================================
# PYDANTIC MODELS (Request/Response Schemas)
# ============================================================================

# VM Models
class VMCreate(BaseModel):
    name: str = Field(..., example="my-vm", description="VM adı")
    image_id: str = Field(..., example="image-uuid", description="Image ID")
    flavor_id: str = Field(..., example="flavor-uuid", description="Flavor ID")
    network_id: str = Field(..., example="network-uuid", description="Network ID")
    key_name: Optional[str] = Field(None, example="my-keypair", description="SSH key pair adı")
    security_groups: Optional[List[str]] = Field(["default"], example=["default"], description="Security group'lar")

class VMResponse(BaseModel):
    id: str
    name: str
    status: str
    addresses: Dict[str, Any]
    flavor: Dict[str, str]
    image: Optional[Dict[str, str]]
    created_at: str

# Project Models
class ProjectCreate(BaseModel):
    name: str = Field(..., example="production", description="Proje adı")
    description: Optional[str] = Field("", example="Production environment", description="Proje açıklaması")
    enabled: bool = Field(True, example=True, description="Proje aktif mi?")

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, example="production-updated", description="Yeni proje adı")
    description: Optional[str] = Field(None, example="Updated description", description="Yeni açıklama")
    enabled: Optional[bool] = Field(None, example=True, description="Aktiflik durumu")

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    enabled: bool

# User Models
class UserCreate(BaseModel):
    name: str = Field(..., example="developer", description="Kullanıcı adı")
    password: str = Field(..., example="SecurePass123!", description="Şifre")
    email: Optional[str] = Field(None, example="dev@example.com", description="E-posta")
    project_id: Optional[str] = Field(None, example="project-uuid", description="Varsayılan proje ID")
    enabled: bool = Field(True, example=True, description="Kullanıcı aktif mi?")

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, example="developer-updated", description="Yeni kullanıcı adı")
    email: Optional[str] = Field(None, example="new@example.com", description="Yeni e-posta")
    password: Optional[str] = Field(None, example="NewPass123!", description="Yeni şifre")
    enabled: Optional[bool] = Field(None, example=True, description="Aktiflik durumu")
    default_project_id: Optional[str] = Field(None, example="project-uuid", description="Varsayılan proje ID")

class UserResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    enabled: bool
    default_project_id: Optional[str]

# Flavor Models
class FlavorCreate(BaseModel):
    name: str = Field(..., example="large", description="Flavor adı")
    ram: int = Field(..., example=4096, description="RAM miktarı (MB)")
    vcpus: int = Field(..., example=2, description="vCPU sayısı")
    disk: int = Field(..., example=40, description="Disk boyutu (GB)")
    is_public: bool = Field(True, example=True, description="Public flavor mı?")

class FlavorResponse(BaseModel):
    id: str
    name: str
    ram: int
    vcpus: int
    disk: int
    is_public: bool

# Network Models
class NetworkCreate(BaseModel):
    name: str = Field(..., example="my-network", description="Network adı")
    admin_state_up: bool = Field(True, example=True, description="Network aktif mi?")
    shared: bool = Field(False, example=False, description="Paylaşımlı network mı?")
    external: bool = Field(False, example=False, description="External network mı?")

class NetworkResponse(BaseModel):
    id: str
    name: str
    status: str
    admin_state_up: bool
    shared: bool
    is_router_external: bool

# Hypervisor Models
class HypervisorResponse(BaseModel):
    id: str
    hypervisor_hostname: str
    status: str
    state: str
    vcpus: int
    vcpus_used: int
    memory_mb: int
    memory_mb_used: int
    running_vms: int

# ============================================================================
# LIST OPERATIONS
# ============================================================================

@router.get("/list/vms", response_model=List[VMResponse], summary="Tüm VM'leri listele")
async def list_vms():
    """Sistemdeki tüm sanal makineleri listeler"""
    try:
        conn = openstack_client.get_connection()
        servers = conn.compute.servers()
        return [
            VMResponse(
                id=s.id,
                name=s.name,
                status=s.status,
                addresses=s.addresses,
                flavor={"id": s.flavor["id"]} if isinstance(s.flavor, dict) else {"id": s.flavor.id},
                image={"id": s.image["id"]} if s.image and isinstance(s.image, dict) else None,
                created_at=s.created_at
            )
            for s in servers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/projects", response_model=List[ProjectResponse], summary="Tüm projeleri listele")
async def list_projects():
    """Sistemdeki tüm projeleri (tenant) listeler"""
    try:
        conn = openstack_client.get_connection()
        projects = conn.identity.projects()
        return [
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description or "",
                enabled=p.is_enabled
            )
            for p in projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/users", response_model=List[UserResponse], summary="Tüm kullanıcıları listele")
async def list_users():
    """Sistemdeki tüm kullanıcıları listeler"""
    try:
        conn = openstack_client.get_connection()
        users = conn.identity.users()
        return [
            UserResponse(
                id=u.id,
                name=u.name,
                email=u.email,
                enabled=u.is_enabled,
                default_project_id=u.default_project_id
            )
            for u in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/flavors", response_model=List[FlavorResponse], summary="Tüm flavor'ları listele")
async def list_flavors():
    """Sistemdeki tüm flavor'ları (VM boyutları) listeler"""
    try:
        conn = openstack_client.get_connection()
        flavors = conn.compute.flavors()
        return [
            FlavorResponse(
                id=f.id,
                name=f.name,
                ram=f.ram,
                vcpus=f.vcpus,
                disk=f.disk,
                is_public=f.is_public
            )
            for f in flavors
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/networks", response_model=List[NetworkResponse], summary="Tüm network'leri listele")
async def list_networks():
    """Sistemdeki tüm network'leri listeler"""
    try:
        conn = openstack_client.get_connection()
        networks = conn.network.networks()
        return [
            NetworkResponse(
                id=n.id,
                name=n.name,
                status=n.status,
                admin_state_up=n.is_admin_state_up,
                shared=n.is_shared,
                is_router_external=n.is_router_external
            )
            for n in networks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# RETRIEVE OPERATIONS
# ============================================================================

@router.get("/retrieve/vm/{vm_id}", response_model=VMResponse, summary="Belirli bir VM'i getir")
async def retrieve_vm(vm_id: str):
    """ID'si verilen sanal makineyi getirir"""
    try:
        conn = openstack_client.get_connection()
        server = conn.compute.get_server(vm_id)
        if not server:
            raise HTTPException(status_code=404, detail="VM not found")
        
        return VMResponse(
            id=server.id,
            name=server.name,
            status=server.status,
            addresses=server.addresses,
            flavor={"id": server.flavor["id"]} if isinstance(server.flavor, dict) else {"id": server.flavor.id},
            image={"id": server.image["id"]} if server.image and isinstance(server.image, dict) else None,
            created_at=server.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/project/{project_id}", response_model=ProjectResponse, summary="Belirli bir projeyi getir")
async def retrieve_project(project_id: str):
    """ID'si verilen projeyi getirir"""
    try:
        conn = openstack_client.get_connection()
        project = conn.identity.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description or "",
            enabled=project.is_enabled
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/user/{user_id}", response_model=UserResponse, summary="Belirli bir kullanıcıyı getir")
async def retrieve_user(user_id: str):
    """ID'si verilen kullanıcıyı getirir"""
    try:
        conn = openstack_client.get_connection()
        user = conn.identity.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            enabled=user.is_enabled,
            default_project_id=user.default_project_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/flavor/{flavor_id}", response_model=FlavorResponse, summary="Belirli bir flavor'ı getir")
async def retrieve_flavor(flavor_id: str):
    """ID'si verilen flavor'ı getirir"""
    try:
        conn = openstack_client.get_connection()
        flavor = conn.compute.get_flavor(flavor_id)
        if not flavor:
            raise HTTPException(status_code=404, detail="Flavor not found")
        
        return FlavorResponse(
            id=flavor.id,
            name=flavor.name,
            ram=flavor.ram,
            vcpus=flavor.vcpus,
            disk=flavor.disk,
            is_public=flavor.is_public
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/network/{network_id}", response_model=NetworkResponse, summary="Belirli bir network'ü getir")
async def retrieve_network(network_id: str):
    """ID'si verilen network'ü getirir"""
    try:
        conn = openstack_client.get_connection()
        network = conn.network.get_network(network_id)
        if not network:
            raise HTTPException(status_code=404, detail="Network not found")
        
        return NetworkResponse(
            id=network.id,
            name=network.name,
            status=network.status,
            admin_state_up=network.is_admin_state_up,
            shared=network.is_shared,
            is_router_external=network.is_router_external
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/hypervisor/{hypervisor_id}", response_model=HypervisorResponse, summary="Belirli bir hypervisor'ı getir")
async def retrieve_hypervisor(hypervisor_id: str):
    """ID'si verilen hypervisor'ı getirir"""
    try:
        conn = openstack_client.get_connection()
        hypervisor = conn.compute.get_hypervisor(hypervisor_id)
        if not hypervisor:
            raise HTTPException(status_code=404, detail="Hypervisor not found")
        
        return HypervisorResponse(
            id=hypervisor.id,
            hypervisor_hostname=hypervisor.name,
            status=hypervisor.status,
            state=hypervisor.state,
            vcpus=hypervisor.vcpus,
            vcpus_used=hypervisor.vcpus_used,
            memory_mb=hypervisor.memory_size,
            memory_mb_used=hypervisor.memory_used,
            running_vms=hypervisor.running_vms
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CREATE OPERATIONS
# ============================================================================

@router.post("/create/vm", response_model=VMResponse, status_code=201, summary="Yeni VM oluştur")
async def create_vm(vm: VMCreate):
    """Yeni bir sanal makine oluşturur"""
    try:
        conn = openstack_client.get_connection()
        
        networks = [{"uuid": vm.network_id}]
        
        # Security groups formatını düzelt
        sec_groups = [{"name": sg} for sg in vm.security_groups] if vm.security_groups else None
        
        new_server = conn.compute.create_server(
            name=vm.name,
            image_id=vm.image_id,
            flavor_id=vm.flavor_id,
            networks=networks,
            key_name=vm.key_name,
            security_groups=sec_groups
        )
        
        # VM'in başlamasını bekle
        new_server = conn.compute.wait_for_server(new_server, status='ACTIVE', wait=300)
        
        return VMResponse(
            id=new_server.id,
            name=new_server.name,
            status=new_server.status,
            addresses=new_server.addresses,
            flavor={"id": new_server.flavor["id"]} if isinstance(new_server.flavor, dict) else {"id": new_server.flavor.id},
            image={"id": new_server.image["id"]} if new_server.image and isinstance(new_server.image, dict) else None,
            created_at=new_server.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create/project", response_model=ProjectResponse, status_code=201, summary="Yeni proje oluştur")
async def create_project(project: ProjectCreate):
    """Yeni bir proje (tenant) oluşturur"""
    try:
        conn = openstack_client.get_connection()
        new_project = conn.identity.create_project(
            name=project.name,
            description=project.description,
            enabled=project.enabled
        )
        return ProjectResponse(
            id=new_project.id,
            name=new_project.name,
            description=new_project.description or "",
            enabled=new_project.is_enabled
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create/user", response_model=UserResponse, status_code=201, summary="Yeni kullanıcı oluştur")
async def create_user(user: UserCreate):
    """Yeni bir kullanıcı oluşturur"""
    try:
        conn = openstack_client.get_connection()
        new_user = conn.identity.create_user(
            name=user.name,
            password=user.password,
            email=user.email,
            default_project_id=user.project_id,
            enabled=user.enabled
        )
        
        # Eğer proje belirtilmişse member rolü ata
        if user.project_id:
            member_role = conn.identity.find_role("member")
            if member_role:
                conn.identity.assign_project_role_to_user(
                    user.project_id,
                    new_user.id,
                    member_role.id
                )
        
        return UserResponse(
            id=new_user.id,
            name=new_user.name,
            email=new_user.email,
            enabled=new_user.is_enabled,
            default_project_id=new_user.default_project_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create/flavor", response_model=FlavorResponse, status_code=201, summary="Yeni flavor oluştur")
async def create_flavor(flavor: FlavorCreate):
    """Yeni bir flavor (VM boyutu) oluşturur"""
    try:
        conn = openstack_client.get_connection()
        new_flavor = conn.compute.create_flavor(
            name=flavor.name,
            ram=flavor.ram,
            vcpus=flavor.vcpus,
            disk=flavor.disk,
            is_public=flavor.is_public
        )
        return FlavorResponse(
            id=new_flavor.id,
            name=new_flavor.name,
            ram=new_flavor.ram,
            vcpus=new_flavor.vcpus,
            disk=new_flavor.disk,
            is_public=new_flavor.is_public
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create/network", response_model=NetworkResponse, status_code=201, summary="Yeni network oluştur")
async def create_network(network: NetworkCreate):
    """Yeni bir network oluşturur"""
    try:
        conn = openstack_client.get_connection()
        new_network = conn.network.create_network(
            name=network.name,
            admin_state_up=network.admin_state_up,
            shared=network.shared,
            is_router_external=network.external
        )
        return NetworkResponse(
            id=new_network.id,
            name=new_network.name,
            status=new_network.status,
            admin_state_up=new_network.is_admin_state_up,
            shared=new_network.is_shared,
            is_router_external=new_network.is_router_external
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# UPDATE OPERATIONS
# ============================================================================

@router.put("/update/project/{project_id}", response_model=ProjectResponse, summary="Projeyi güncelle")
async def update_project(project_id: str, project: ProjectUpdate):
    """Mevcut bir projeyi günceller"""
    try:
        conn = openstack_client.get_connection()
        
        # Önce projeyi al
        existing_project = conn.identity.get_project(project_id)
        if not existing_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Güncelleme verilerini hazırla (sadece None olmayanlar)
        update_data = {}
        if project.name is not None:
            update_data['name'] = project.name
        if project.description is not None:
            update_data['description'] = project.description
        if project.enabled is not None:
            update_data['enabled'] = project.enabled
        
        # Güncelle
        updated_project = conn.identity.update_project(project_id, **update_data)
        
        return ProjectResponse(
            id=updated_project.id,
            name=updated_project.name,
            description=updated_project.description or "",
            enabled=updated_project.is_enabled
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update/user/{user_id}", response_model=UserResponse, summary="Kullanıcıyı güncelle")
async def update_user(user_id: str, user: UserUpdate):
    """Mevcut bir kullanıcıyı günceller"""
    try:
        conn = openstack_client.get_connection()
        
        # Önce kullanıcıyı al
        existing_user = conn.identity.get_user(user_id)
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Güncelleme verilerini hazırla (sadece None olmayanlar)
        update_data = {}
        if user.name is not None:
            update_data['name'] = user.name
        if user.email is not None:
            update_data['email'] = user.email
        if user.password is not None:
            update_data['password'] = user.password
        if user.enabled is not None:
            update_data['enabled'] = user.enabled
        if user.default_project_id is not None:
            update_data['default_project_id'] = user.default_project_id
        
        # Güncelle
        updated_user = conn.identity.update_user(user_id, **update_data)
        
        return UserResponse(
            id=updated_user.id,
            name=updated_user.name,
            email=updated_user.email,
            enabled=updated_user.is_enabled,
            default_project_id=updated_user.default_project_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))