def get_min_role(min_role: str, allow_super_user: bool = True):
    """
    Factory function for a dependency that ensures:
    1. User has at least min_role in a specified workspace (if applicable).
    2. Optionally restricts super_user access based on allow_super_user.

    Parameters:
    - min_role: The minimum role required for the operation.
    - allow_super_user: If True (default), super_user bypasses all checks.
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
        Validate the user's role for the specified workspace and domain (if applicable).
        """
        # 1. Restrict super_user if allow_super_user is False
        if user.is_super_user and not allow_super_user:
            raise HTTPException(
                status_code=403, detail="Access Denied: Super user access is restricted for this route."
            )

        # 2. Short-circuit if the user is a super_user and allow_super_user is True
        if user.is_super_user:
            return user

        # 3. Extract workspace_id and domain_id from path or body
        workspace_id: Optional[UUID] = request.path_params.get("workspace_id")
        domain_id: Optional[UUID] = request.path_params.get("domain_id")

        # Parse request body for POST/PUT/PATCH
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = request.json()
                if "workspace_id" in body and not workspace_id:
                    workspace_id = body["workspace_id"]
                if "domain_id" in body and not domain_id:
                    domain_id = body["domain_id"]
            except:
                pass  # No body or invalid JSON

        # 4. Workspace role check (if workspace_id is provided)
        if workspace_id:
            user_workspace = session.query(UserWorkspaceLink).filter_by(
                user_id=user.id, workspace_id=workspace_id
            ).first()

            # Default to app_user if the user has no explicit workspace role
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

        # 5. Domain membership check (only if min_role is "domain_admin")
        if min_role == "domain_admin":
            if not domain_id:
                raise HTTPException(
                    status_code=400, detail="Domain ID is required but not provided."
                )

            if not workspace_id:
                raise HTTPException(
                    status_code=400,
                    detail="Workspace ID is required for domain validation.",
                )

            domain_link = session.query(UserWorkspaceDomainLink).filter_by(
                user_workspace_id=user_workspace.domain_mapping_id, domain_id=domain_id
            ).first()

            if not domain_link:
                raise HTTPException(
                    status_code=403,
                    detail="Access Denied: You are not associated with the specified domain.",
                )

        # 6. Return user if all checks pass or no workspace validation is needed
        return user

    return access_min_role
