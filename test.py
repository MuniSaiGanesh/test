def get_min_role(min_role: str, allow_super_user: bool = True):
    """
    Factory function for a dependency that ensures:
    - Dynamically validates workspace and domain based on the context.
    """
    if min_role not in Role_Rank:
        raise ValueError(f"Invalid role specified: {min_role}")
    min_role_rank = Role_Rank[min_role]

    def access_min_role(
        request: Request,
        user: User = Depends(get_current_user),
        session: Session = Depends(get_db),
    ) -> User:
        """
        Validate the user's role for the specified workspace and domain.
        """
        # Handle super_user access
        if user.is_super_user and not allow_super_user:
            raise HTTPException(
                status_code=403, detail="Access Denied: Super user access is restricted for this route."
            )

        if user.is_super_user:
            return user

        # Extract workspace_id and domain_id
        workspace_id: Optional[UUID] = request.path_params.get("workspace_id")
        domain_id: Optional[UUID] = request.path_params.get("domain_id")

        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = request.json()
                if "workspace_id" in body and not workspace_id:
                    workspace_id = body["workspace_id"]
                if "domain_id" in body and not domain_id:
                    domain_id = body["domain_id"]
            except:
                pass  # Body parsing failed; skip workspace_id and domain_id

        # Skip workspace validation if no workspace_id is required
        if min_role == "app_user" and not workspace_id:
            return user

        # Perform workspace validation if workspace_id is provided
        if workspace_id:
            user_workspace = session.query(UserWorkspaceLink).filter_by(
                user_id=user.id, workspace_id=workspace_id
            ).first()

            if not user_workspace:
                user_workspace_role = "app_user"
            else:
                user_workspace_role = user_workspace.role.value

            user_workspace_rank = Role_Rank.get(user_workspace_role, Role_Rank["app_user"])

            if user_workspace_rank > min_role_rank:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Access Denied: Workspace role '{user_workspace_role}' "
                        f"insufficient for required role '{min_role}'."
                    ),
                )

        # Perform domain validation if domain_id is present and role requires it
        if domain_id and min_role == "domain_admin":
            user_workspace = session.query(UserWorkspaceLink).filter_by(
                user_id=user.id, workspace_id=workspace_id
            ).first()

            if not user_workspace:
                raise HTTPException(
                    status_code=403,
                    detail="Access Denied: User is not associated with the specified workspace.",
                )

            domain_link = session.query(UserWorkspaceDomainLink).filter_by(
                user_workspace_id=user_workspace.domain_mapping_id, domain_id=domain_id
            ).first()

            if not domain_link:
                raise HTTPException(
                    status_code=403,
                    detail="Access Denied: You are not associated with the specified domain.",
                )

        return user

    return access_min_role
