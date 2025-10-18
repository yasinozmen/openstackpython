from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.openstack_client import openstack_client
from app import operations, maintenance

# FastAPI uygulamasını oluştur
app = FastAPI(
    title="OpenStack Management API",
    description="""
    ## OpenStack Kaynak Yönetim API'si (Controller Node Edition)
    
    Bu API OpenStack Controller Node üzerinde çalışır ve tüm OpenStack kaynaklarını yönetir.
    
    ### 📋 List Operations
    * **VMs** - Tüm sanal makineleri listele
    * **Projects** - Tüm projeleri listele
    * **Users** - Tüm kullanıcıları listele
    * **Flavors** - Tüm flavor'ları listele
    * **Networks** - Tüm network'leri listele
    
    ### 🔍 Retrieve Operations
    * **VM** - Belirli bir VM'i getir
    * **Project** - Belirli bir projeyi getir
    * **User** - Belirli bir kullanıcıyı getir
    * **Flavor** - Belirli bir flavor'ı getir
    * **Network** - Belirli bir network'ü getir
    * **Hypervisor** - Belirli bir hypervisor'ı getir
    
    ### ➕ Create Operations
    * **VM** - Yeni sanal makine oluştur
    * **Project** - Yeni proje oluştur
    * **User** - Yeni kullanıcı oluştur
    * **Flavor** - Yeni flavor oluştur
    * **Network** - Yeni network oluştur
    
    ### ✏️ Update Operations
    * **Project** - Projeyi güncelle
    * **User** - Kullanıcıyı güncelle
    
    ### 🔧 Maintenance Operations
    * **Drain** - Hypervisor bakım modu (VM migration)
    * **Hypervisor Status** - Kaynak kullanım bilgileri
    
    ---
    
    **Deployment:** Controller Node (Localhost OpenStack API)
    
    **Version:** 1.0.0
    """,
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS middleware ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da bunu sınırla
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(operations.router)
app.include_router(maintenance.router)

@app.on_event("startup")
async def startup_event():
    """Uygulama başlarken OpenStack bağlantısını test et"""
    print("=" * 70)
    print("🚀 OpenStack FastAPI - Controller Node Edition")
    print("=" * 70)
    print(f"📍 Auth URL: {settings.OS_AUTH_URL}")
    print(f"👤 Username: {settings.OS_USERNAME}")
    print(f"🏢 Project: {settings.OS_PROJECT_NAME}")
    print("-" * 70)
    
    if openstack_client.test_connection():
        print("✅ OpenStack bağlantısı başarılı!")
    else:
        print("❌ OpenStack bağlantısı başarısız!")
        print("⚠️  Lütfen .env dosyasını ve OpenStack servislerini kontrol edin.")
    
    print("-" * 70)
    print(f"📖 Swagger UI: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print(f"📖 ReDoc: http://{settings.API_HOST}:{settings.API_PORT}/redoc")
    print("=" * 70)

@app.get("/", tags=["Root"])
async def root():
    """Ana endpoint - API bilgileri"""
    return {
        "message": "OpenStack Management API",
        "version": "1.0.0",
        "deployment": "Controller Node Edition",
        "auth_url": settings.OS_AUTH_URL,
        "project": settings.OS_PROJECT_NAME,
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    connection_ok = openstack_client.test_connection()
    
    return {
        "status": "healthy" if connection_ok else "unhealthy",
        "openstack_connection": connection_ok,
        "auth_url": settings.OS_AUTH_URL,
        "project": settings.OS_PROJECT_NAME,
        "api_version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
