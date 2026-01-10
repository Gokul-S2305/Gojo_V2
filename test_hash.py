from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

try:
    hash = pwd_context.hash("testpassword")
    print(f"Hash success: {hash}")
except Exception as e:
    print(f"Hash failed: {e}")
    import traceback
    traceback.print_exc()
