import openstack
from openstack.connection import Connection
from app.config import settings

class OpenStackClient:
    _connection: Connection = None
    
    @classmethod
    def get_connection(cls) -> Connection:
        """OpenStack bağlantısını singleton olarak döndürür"""
        if cls._connection is None:
            cls._connection = openstack.connect(
                auth_url=settings.OS_AUTH_URL,
                project_name=settings.OS_PROJECT_NAME,
                username=settings.OS_USERNAME,
                password=settings.OS_PASSWORD,
                user_domain_name=settings.OS_USER_DOMAIN_NAME,
                project_domain_name=settings.OS_PROJECT_DOMAIN_NAME,
                identity_api_version=settings.OS_IDENTITY_API_VERSION,
                app_name='openstack-fastapi',
                app_version='1.0'
            )
        return cls._connection
    
    @classmethod
    def test_connection(cls) -> bool:
        """Bağlantıyı test eder"""
        try:
            conn = cls.get_connection()
            list(conn.identity.projects())
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

# Global instance
openstack_client = OpenStackClient()