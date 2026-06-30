"""Organization API routes (§7)."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import AuthContext, get_current_user
from app.db import models, session
from app.invoices import service
from app.billing import usage

router = APIRouter(prefix="/api", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str
    slug: str
    billing_email: str | None = None


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    subscription_status: str
    billing_email: str | None = None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "org"


@router.post("/organizations", response_model=OrgOut, status_code=201)
def create_org(req: OrgCreate, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    user = service.ensure_user_profile(db, auth)
    slug = _slugify(req.slug or req.name)
    existing = db.execute(select(models.Organization).where(models.Organization.slug == slug)).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Slug already taken")
    org = models.Organization(name=req.name, slug=slug, billing_email=req.billing_email)
    db.add(org)
    db.flush()
    db.add(models.OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    return OrgOut(id=str(org.id), name=org.name, slug=org.slug, plan=org.plan,
                  subscription_status=org.subscription_status, billing_email=org.billing_email)


@router.get("/organizations", response_model=list[OrgOut])
def list_orgs(auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    user = service.ensure_user_profile(db, auth)
    rows = db.execute(
        select(models.Organization, models.OrganizationMember.role)
        .join(models.OrganizationMember, models.OrganizationMember.organization_id == models.Organization.id)
        .where(models.OrganizationMember.user_id == user.id)
    ).all()
    out = []
    for org, role in rows:
        out.append(OrgOut(id=str(org.id), name=org.name, slug=org.slug, plan=org.plan,
                          subscription_status=org.subscription_status, billing_email=org.billing_email))
    return out


@router.get("/organizations/{org_id}", response_model=OrgOut)
def get_org(org_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    org, _ = service._require_member(db, auth, org_id)
    return OrgOut(id=str(org.id), name=org.name, slug=org.slug, plan=org.plan,
                  subscription_status=org.subscription_status, billing_email=org.billing_email)


@router.get("/organizations/{org_id}/members")
def list_members(org_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    service._require_member(db, auth, org_id)
    rows = db.execute(
        select(models.OrganizationMember, models.User)
        .join(models.User, models.User.id == models.OrganizationMember.user_id)
        .where(models.OrganizationMember.organization_id == uuid.UUID(org_id))
    ).all()
    return [{"id": str(m.id), "user_id": str(u.id), "email": u.email, "role": m.role} for m, u in rows]


class MemberUpdate(BaseModel):
    role: str


@router.patch("/organizations/{org_id}/members/{member_id}")
def update_member(org_id: str, member_id: str, payload: MemberUpdate,
                  auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    _, member = service._require_member(db, auth, org_id)
    if member.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners/admins can change roles")
    if payload.role not in ("owner", "admin", "member", "viewer"):
        raise HTTPException(400, "Invalid role")
    target = db.get(models.OrganizationMember, uuid.UUID(member_id))
    if not target or target.organization_id != uuid.UUID(org_id):
        raise HTTPException(404, "Member not found")
    # prevent demoting the last owner
    if target.role == "owner" and payload.role != "owner":
        owners = db.execute(select(models.OrganizationMember).where(
            models.OrganizationMember.organization_id == uuid.UUID(org_id),
            models.OrganizationMember.role == "owner",
        )).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(400, "Cannot demote the last owner")
    target.role = payload.role
    db.commit()
    return {"id": str(target.id), "role": target.role}