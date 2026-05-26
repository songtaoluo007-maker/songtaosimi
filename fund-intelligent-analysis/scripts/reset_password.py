"""
命令行密码重置工具
用法: python scripts/reset_password.py [username]
不指定用户名则重置 owner 角色账号
"""
import sys
sys.path.insert(0, '.')
from backend.database import SessionLocal, init_db
from backend.models.user import UserAccount
from backend.services.auth_service import hash_password

init_db()
db = SessionLocal()
target = sys.argv[1] if len(sys.argv) > 1 else None

user = None
if target:
    user = db.query(UserAccount).filter(UserAccount.username == target).first()
else:
    user = db.query(UserAccount).filter(UserAccount.role == "owner").first()

if not user:
    print("未找到账号。可用账号：")
    for u in db.query(UserAccount).all():
        print(f"  {u.username} ({u.display_name})")
    db.close()
    sys.exit(1)

new_password = input(f"为用户 {user.username} 输入新密码: ").strip()
if len(new_password) < 8:
    print("密码至少需要 8 位")
    db.close()
    sys.exit(1)

user.password_hash = hash_password(new_password)
user.failed_login_count = 0
user.locked_until = None
db.commit()
print(f"密码已重置。用户名: {user.username}")
db.close()
