from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import SessionLocal, get_db
from models import Domain, User, UserDomainLink, DomainDatasourceLink
from schemas import DomainCreate

router = APIRouter(
    prefix="/domains",
    tags=["Domains"]
)

class DomainBase(BaseModel):
    name: str

class DomainCreate(DomainBase):
    pass

class Domain(DomainBase):
    id: int

    class Config:
        orm_mode = True

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_domain(domain: DomainCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Create a new domain for the current user.
    """

    # Check if domain with the same name already exists for the user
    existing_domain = db.query(Domain).join(UserDomainLink).filter(
        Domain.name == domain.name,
        UserDomainLink.user_id == current_user.id
    ).first()

    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain with this name already exists for the user."
        )

    # Create the new domain
    new_domain = Domain(name=domain.name)
    db.add(new_domain)
    db.commit()
    db.refresh(new_domain)

    # Link the domain to the current user
    user_domain_link = UserDomainLink(user_id=current_user.id, domain_id=new_domain.id)
    db.add(user_domain_link)
    db.commit()

    # Check for existing DomainDatasourceLink (if applicable)
    # ... (Logic to check for existing DomainDatasourceLink) ...

    return new_domain
