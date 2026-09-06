"""KAP bildirim API cikti semalari."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KapAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    obj_id: str
    file_name: str
    file_extension: str | None
    size_bytes: int | None
    sha256: str | None
    downloaded_at: datetime | None
    download_error: str | None


class KapDisclosureListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    disclosure_index: int
    published_at: datetime
    kap_title: str
    subject: str | None
    summary: str | None
    disclosure_class: str | None
    disclosure_type: str | None
    disclosure_category: str | None
    ticker_codes: list[str]
    is_late: bool
    attachment_count: int


class KapDisclosureDetailOut(KapDisclosureListOut):
    body_html: str | None
    body_text: str | None
    attachments: list[KapAttachmentOut]
