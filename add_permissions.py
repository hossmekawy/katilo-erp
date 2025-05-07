from app import app, db, Role, Permission, RolePermission

def add_all_permissions_to_admin():
    with app.app_context():
        # Get admin role
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            print("Admin role not found")
            return
        
        # Get all permissions
        permissions = Permission.query.all()
        
        # Get existing role permissions
        existing_role_permissions = RolePermission.query.filter_by(role_id=admin_role.id).all()
        existing_permission_ids = [rp.permission_id for rp in existing_role_permissions]
        
        # Add missing permissions
        added_count = 0
        for permission in permissions:
            if permission.id not in existing_permission_ids:
                role_permission = RolePermission(
                    role_id=admin_role.id,
                    permission_id=permission.id
                )
                db.session.add(role_permission)
                added_count += 1
        
        if added_count > 0:
            db.session.commit()
            print(f"Added {added_count} permissions to admin role")
        else:
            print("Admin role already has all permissions")

if __name__ == "__main__":
    add_all_permissions_to_admin()
