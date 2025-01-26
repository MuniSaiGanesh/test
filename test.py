
def create_domain(db: Session, domain_data: DomainCreate) -> Domain:
    """
    Creates a new domain entry in the database.

    Args:
        db (Session): The database session.
        domain_data (DomainCreate): The domain creation data.

    Returns:
        Domain: The newly created domain.
    """
    # Initialize the Domain object with the provided data
    new_domain = Domain(
        name=domain_data.name,
        description=domain_data.description,
        purpose=domain_data.purpose,
        is_active=domain_data.is_active,
        workspace_id=domain_data.workspace_id,
        connection_id=domain_data.connection_id,
        default_llm_provider=domain_data.default_llm_provider,
        default_llm_model=domain_data.default_llm_model,
        last_updated_date=datetime.now(timezone.utc),
        last_metadata_refresh_date=datetime.now(timezone.utc),
        last_metadata_update_date=datetime.now(timezone.utc),
        knowledgebase_validation_status="INPROGRESS"
    )

    # Add tags if provided
    if domain_data.tags:
        new_domain.tags = domain_data.tags

    # Handle datasources (many-to-many relationship via DomainDatasourceLink)
    if domain_data.datasource_ids:
        for datasource_id in domain_data.datasource_ids:
            link = DomainDatasourceLink(domain_id=new_domain.id, datasource_id=datasource_id)
            db.add(link)

    # Handle knowledge docs (embedded structure in InputData)
    if domain_data.knowledge_docs:
        knowledge_base_items = []
        for target_response in domain_data.knowledge_docs.target_response:
            knowledge_base_items.append(
                {
                    "knowledgebase_type": "target_response",
                    "value": {
                        "question": target_response.question,
                        "sql_query": target_response.sql_query,
                        "is_valid": target_response.is_valid,
                        "message": target_response.message,
                    },
                }
            )
        for kpi_definition in domain_data.knowledge_docs.kpi_definitions:
            knowledge_base_items.append(
                {
                    "knowledgebase_type": "kpi_definition",
                    "value": {
                        "kpi_name": kpi_definition.kpi_name,
                        "kpi_description": kpi_definition.kpi_description,
                        "kpi_formula": kpi_definition.kpi_formula,
                        "is_valid": kpi_definition.is_valid,
                        "message": kpi_definition.message,
                    },
                }
            )
        for item in knowledge_base_items:
            knowledge_base = KnowledgeBase(
                domain_id=new_domain.id,
                knowledgebase_type=item["knowledgebase_type"],
                value=item["value"],
                status="INPROGRESS",
                knowledgebase_chunk_id=uuid4()
            )
            db.add(knowledge_base)

    # Add the new domain to the session and commit
    db.add(new_domain)
    db.commit()
    db.refresh(new_domain)  # Refresh to get the latest data including the generated ID

    return new_domain


def add_datasource(db: Session, domain_id: UUID, datasource_ids: List[UUID]) -> Domain:
    """
    Adds one or more datasources to an existing domain.

    Args:
        db (Session): The database session.
        domain_id (UUID): The ID of the domain to which datasources will be added.
        datasource_ids (List[UUID]): A list of datasource IDs to add.

    Returns:
        Domain: The updated domain with the added datasources.
    """
    # Retrieve the domain by ID
    domain = db.get(Domain, domain_id)
    if not domain:
        raise ValueError(f"Domain with ID {domain_id} not found.")

    # Add the datasource links
    for datasource_id in datasource_ids:
        link = DomainDatasourceLink(domain_id=domain_id, datasource_id=datasource_id)
        db.add(link)

    # Commit the changes
    db.commit()
    db.refresh(domain)  # Refresh to include the new links

    return domain
