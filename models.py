from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base

class TargetDomain(Base):
    __tablename__ = "targets"
    id = Column(Integer, primary_key=True)
    domain = Column(String, unique=True, index=True)
    brand = Column(String, index=True)
    homepage_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=False, index=True)
    scan_interval_minutes = Column(Integer, default=15)
    last_scan_started = Column(DateTime)
    last_scan_finished = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

class ScanJob(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey("targets.id"))
    status = Column(String, default="QUEUED")
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)
    target = relationship("TargetDomain")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey("targets.id"), index=True)
    source = Column(String)
    fqdn = Column(String, index=True)
    url = Column(String)
    tld = Column(String)
    registrable_domain = Column(String)
    label = Column(String)
    reason = Column(String)
    score = Column(Float)

    metadata_json = Column("metadata", JSON)  # correct JSON column name
    html_hash = Column(String)
    html_sim = Column(Float)
    img_phash = Column(String)
    img_sim = Column(Float)
    screenshot_path = Column(String)
    original_screenshot_path = Column(String)

    created_at = Column(DateTime, server_default=func.now())
    target = relationship("TargetDomain")