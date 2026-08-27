"""Declarative specs for every ITFlow v1 API module.

The specs drive automatic generation of MCP tools: one tool per
``{module}_{function}`` pair. Field lists follow the module reference at
https://docs.itflow.org/api.

Conventions
-----------
- ``field(name, kind, description, required=False, default=None)``
- ``kind`` is one of ``"int"``, ``"str"``, ``"float"``, ``"bool"``.
- ``required`` marks fields the docs say must be present (ITFlow still
  accepts partial creates for most modules).
- ``client_id`` is required on POST only when the API key has all-client
  scope; the docs mark it ``Yes*``. It is therefore optional here but
  documented, and the server injects nothing - the caller decides.
- The ``api_key`` (and for credentials, ``api_key_decrypt_password``)
  fields are always supplied by the server from environment variables and
  are never exposed as tool parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any


@dataclass(frozen=True)
class Field:
    name: str
    kind: str  # "int" | "str" | "float" | "bool"
    description: str
    required: bool = False
    default: Any = None


@dataclass(frozen=True)
class FunctionSpec:
    name: str  # read, create, update, delete, archive, unarchive, resolve
    description: str
    fields: tuple[Field, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class ModuleSpec:
    name: str  # URL path segment, e.g. "assets"
    purpose: str
    functions: tuple[FunctionSpec, ...]


def f(name: str, kind: str, description: str, required: bool = False, default: Any = None) -> Field:
    return Field(name=name, kind=kind, description=description, required=required, default=default)


def _read(fields: tuple[Field, ...], notes: str = "") -> FunctionSpec:
    return FunctionSpec("read", "List or fetch records. Returns up to `limit` rows (default 50); paginate with `offset`.", fields=fields, notes=notes)


def _client_id(required_note: bool = True) -> Field:
    return f(
        "client_id",
        "int",
        "Client the record belongs to. Required when the API key has all-client scope.",
    )


CLIENT_ID = _client_id()

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        name="assets",
        purpose="Computer and equipment inventory management.",
        functions=(
            _read(
                (
                    f("asset_id", "int", "Get a specific asset by ID."),
                    f("asset_type", "str", "Filter by asset type (auto-capitalized by ITFlow)."),
                    f("asset_name", "str", "Filter by exact asset name."),
                    f("asset_serial", "str", "Filter by serial number."),
                    f("asset_mac", "str", "Filter by MAC address (searches primary interface)."),
                    f("asset_uri", "str", "Filter by management URI."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a new asset record.",
                fields=(
                    CLIENT_ID,
                    f("asset_name", "str", "Asset name/hostname.", required=True),
                    f("asset_description", "str", "Asset description."),
                    f("asset_type", "str", "Type (Laptop, Desktop, Server, etc.)."),
                    f("asset_make", "str", "Manufacturer."),
                    f("asset_model", "str", "Model name/number."),
                    f("asset_serial", "str", "Serial number."),
                    f("asset_os", "str", "Operating system."),
                    f("asset_ip", "str", "IP address (stored in primary interface)."),
                    f("asset_mac", "str", "MAC address (stored in primary interface)."),
                    f("asset_uri", "str", "Management URL."),
                    f("asset_status", "str", "Status (Deployed, Spare, etc.)."),
                    f("asset_purchase_date", "str", "Purchase date (YYYY-MM-DD)."),
                    f("asset_warranty_expire", "str", "Warranty expiration date (YYYY-MM-DD)."),
                    f("asset_install_date", "str", "Installation date (YYYY-MM-DD)."),
                    f("asset_notes", "str", "Notes."),
                    f("asset_vendor_id", "int", "Associated vendor ID."),
                    f("asset_location_id", "int", "Associated location ID."),
                    f("asset_contact_id", "int", "Associated contact ID."),
                    f("asset_network_id", "int", "Network ID for primary interface."),
                ),
            ),
            FunctionSpec(
                "update",
                "Update an existing asset. Only provided fields are changed.",
                fields=(
                    f("asset_id", "int", "ID of the asset to update.", required=True),
                    CLIENT_ID,
                    f("asset_name", "str", "Asset name/hostname."),
                    f("asset_description", "str", "Asset description."),
                    f("asset_type", "str", "Type (Laptop, Desktop, Server, etc.)."),
                    f("asset_make", "str", "Manufacturer."),
                    f("asset_model", "str", "Model name/number."),
                    f("asset_serial", "str", "Serial number."),
                    f("asset_os", "str", "Operating system."),
                    f("asset_ip", "str", "IP address (stored in primary interface)."),
                    f("asset_mac", "str", "MAC address (stored in primary interface)."),
                    f("asset_uri", "str", "Management URL."),
                    f("asset_status", "str", "Status (Deployed, Spare, etc.)."),
                    f("asset_purchase_date", "str", "Purchase date (YYYY-MM-DD)."),
                    f("asset_warranty_expire", "str", "Warranty expiration date (YYYY-MM-DD)."),
                    f("asset_install_date", "str", "Installation date (YYYY-MM-DD)."),
                    f("asset_notes", "str", "Notes."),
                    f("asset_vendor_id", "int", "Associated vendor ID."),
                    f("asset_location_id", "int", "Associated location ID."),
                    f("asset_contact_id", "int", "Associated contact ID."),
                    f("asset_network_id", "int", "Network ID for primary interface."),
                ),
            ),
            FunctionSpec(
                "delete",
                "Delete an asset record. Also removes all associated network interfaces.",
                fields=(f("asset_id", "int", "ID of the asset to delete.", required=True), CLIENT_ID),
            ),
        ),
    ),
    ModuleSpec(
        name="certificates",
        purpose="SSL/TLS certificate management and expiration tracking.",
        functions=(
            _read(
                (
                    f("certificate_id", "int", "Get a specific certificate by ID."),
                    f("certificate_name", "str", "Filter by certificate name."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a certificate record. Update/delete are not implemented for this module.",
                fields=(
                    CLIENT_ID,
                    f("certificate_name", "str", "Certificate friendly name.", required=True),
                    f("certificate_domain", "str", "Domain the certificate covers.", required=True),
                    f("certificate_description", "str", "Description."),
                    f("certificate_issued_by", "str", "Issuing authority (e.g., Let's Encrypt)."),
                    f("certificate_expire", "str", "Expiration date (YYYY-MM-DD)."),
                    f("certificate_public_key", "str", "Certificate content/public key."),
                    f("certificate_notes", "str", "Additional notes."),
                    f("certificate_domain_id", "int", "Link to a domains table record."),
                ),
            ),
        ),
    ),
    ModuleSpec(
        name="clients",
        purpose="Customer/company management. Delete is not implemented - use archive.",
        functions=(
            _read(
                (
                    f("client_name", "str", "Get a specific client by exact name."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                ),
                notes="Creating clients requires an API key with all-client scope (client_id = 0).",
            ),
            FunctionSpec(
                "create",
                "Create a new client. Requires an API key with all-client scope.",
                fields=(
                    f("client_name", "str", "Client/company name.", required=True),
                    f("client_type", "str", "Business type/category."),
                    f("client_website", "str", "Website URL (https:// prefix auto-removed)."),
                    f("client_referral", "str", "Referral source."),
                    f("client_rate", "float", "Hourly rate."),
                    f("client_currency_code", "str", "Currency code (e.g., USD)."),
                    f("client_net_terms", "int", "Payment terms in days."),
                    f("client_tax_id_number", "str", "Tax ID/EIN."),
                    f("client_abbreviation", "str", "Short code (max 6 chars)."),
                    f("client_is_lead", "int", "Lead flag (0 or 1)."),
                    f("client_notes", "str", "Additional notes."),
                ),
                notes="Only available with an all-client-scoped API key.",
            ),
            FunctionSpec(
                "update",
                "Update client details. Only provided fields are changed.",
                fields=(
                    f("client_id", "int", "ID of the client to update.", required=True),
                    f("client_name", "str", "Client/company name."),
                    f("client_type", "str", "Business type/category."),
                    f("client_website", "str", "Website URL (https:// prefix auto-removed)."),
                    f("client_referral", "str", "Referral source."),
                    f("client_rate", "float", "Hourly rate."),
                    f("client_currency_code", "str", "Currency code (e.g., USD)."),
                    f("client_net_terms", "int", "Payment terms in days."),
                    f("client_tax_id_number", "str", "Tax ID/EIN."),
                    f("client_abbreviation", "str", "Short code (max 6 chars)."),
                    f("client_is_lead", "int", "Lead flag (0 or 1)."),
                    f("client_notes", "str", "Additional notes."),
                ),
            ),
            FunctionSpec(
                "archive",
                "Archive a client. Automatically stops all recurring invoices for that client.",
                fields=(f("client_id", "int", "ID of the client to archive.", required=True),),
            ),
            FunctionSpec(
                "unarchive",
                "Unarchive a previously archived client.",
                fields=(f("client_id", "int", "ID of the client to unarchive.", required=True),),
            ),
        ),
    ),
    ModuleSpec(
        name="contacts",
        purpose="Individual contact management within client organizations.",
        functions=(
            _read(
                (
                    f("contact_id", "int", "Get a specific contact by ID."),
                    f("contact_email", "str", "Get a contact by email address."),
                    f("contact_phone_or_mobile", "str", "Get a contact by phone or mobile number."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a new contact.",
                fields=(
                    CLIENT_ID,
                    f("contact_name", "str", "Full name.", required=True),
                    f("contact_email", "str", "Email address (must be unique per client).", required=True),
                    f("contact_title", "str", "Job title."),
                    f("contact_department", "str", "Department."),
                    f("contact_phone", "str", "Phone number (non-digits stripped)."),
                    f("contact_extension", "str", "Phone extension."),
                    f("contact_mobile", "str", "Mobile number (non-digits stripped)."),
                    f("contact_notes", "str", "Notes."),
                    f("contact_primary", "int", "Primary contact flag (0 or 1). Setting 1 removes the flag from other contacts for this client."),
                    f("contact_important", "int", "Important flag (0 or 1)."),
                    f("contact_billing", "int", "Billing contact flag (0 or 1)."),
                    f("contact_technical", "int", "Technical contact flag (0 or 1)."),
                    f("contact_location_id", "int", "Associated location ID."),
                ),
            ),
            FunctionSpec(
                "update",
                "Update contact details. Only provided fields are changed.",
                fields=(
                    f("contact_id", "int", "ID of the contact to update.", required=True),
                    CLIENT_ID,
                    f("contact_name", "str", "Full name."),
                    f("contact_email", "str", "Email address (must be unique per client)."),
                    f("contact_title", "str", "Job title."),
                    f("contact_department", "str", "Department."),
                    f("contact_phone", "str", "Phone number (non-digits stripped)."),
                    f("contact_extension", "str", "Phone extension."),
                    f("contact_mobile", "str", "Mobile number (non-digits stripped)."),
                    f("contact_notes", "str", "Notes."),
                    f("contact_primary", "int", "Primary contact flag (0 or 1)."),
                    f("contact_important", "int", "Important flag (0 or 1)."),
                    f("contact_billing", "int", "Billing contact flag (0 or 1)."),
                    f("contact_technical", "int", "Technical contact flag (0 or 1)."),
                    f("contact_location_id", "int", "Associated location ID."),
                ),
            ),
            FunctionSpec(
                "delete",
                "Delete a contact record.",
                fields=(f("contact_id", "int", "ID of the contact to delete.", required=True), CLIENT_ID),
            ),
            FunctionSpec(
                "archive",
                "Archive a contact. Also archives their associated user account if one exists.",
                fields=(f("contact_id", "int", "ID of the contact to archive.", required=True),),
            ),
            FunctionSpec(
                "unarchive",
                "Unarchive a previously archived contact.",
                fields=(f("contact_id", "int", "ID of the contact to unarchive.", required=True),),
            ),
        ),
    ),
    ModuleSpec(
        name="credentials",
        purpose="Password and login management (encrypted storage). All operations require the API key's decrypt password, which is supplied automatically from ITFLOW_API_KEY_PASSWORD. Delete is not implemented.",
        functions=(
            _read(
                (
                    f("credential_id", "int", "Get a specific credential by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                ),
                notes="Requires ITFLOW_API_KEY_PASSWORD to be set.",
            ),
            FunctionSpec(
                "create",
                "Create a new credential record (password stored encrypted by ITFlow).",
                fields=(
                    CLIENT_ID,
                    f("credential_name", "str", "Credential name/label.", required=True),
                    f("credential_password", "str", "Password (will be encrypted).", required=True),
                    f("credential_description", "str", "Description."),
                    f("credential_uri", "str", "Login URL."),
                    f("credential_uri_2", "str", "Secondary URL."),
                    f("credential_username", "str", "Username (will be encrypted)."),
                    f("credential_otp_secret", "str", "TOTP/2FA secret."),
                    f("credential_note", "str", "Additional notes."),
                    f("credential_important", "int", "Important flag (0 or 1)."),
                    f("credential_contact_id", "int", "Associated contact ID."),
                    f("credential_vendor_id", "int", "Associated vendor ID."),
                    f("credential_asset_id", "int", "Associated asset ID."),
                    f("credential_software_id", "int", "Associated software ID."),
                ),
                notes="Requires ITFLOW_API_KEY_PASSWORD to be set.",
            ),
            FunctionSpec(
                "update",
                "Update a credential. Updating the password refreshes its changed-at timestamp.",
                fields=(
                    f("credential_id", "int", "ID of the credential to update.", required=True),
                    CLIENT_ID,
                    f("credential_name", "str", "Credential name/label."),
                    f("credential_password", "str", "New password (will be encrypted)."),
                    f("credential_description", "str", "Description."),
                    f("credential_uri", "str", "Login URL."),
                    f("credential_uri_2", "str", "Secondary URL."),
                    f("credential_username", "str", "Username (will be encrypted)."),
                    f("credential_otp_secret", "str", "TOTP/2FA secret."),
                    f("credential_note", "str", "Additional notes."),
                    f("credential_important", "int", "Important flag (0 or 1)."),
                    f("credential_contact_id", "int", "Associated contact ID."),
                    f("credential_vendor_id", "int", "Associated vendor ID."),
                    f("credential_asset_id", "int", "Associated asset ID."),
                    f("credential_software_id", "int", "Associated software ID."),
                ),
                notes="Requires ITFLOW_API_KEY_PASSWORD to be set.",
            ),
        ),
    ),
    ModuleSpec(
        name="documents",
        purpose="Internal documentation and knowledge base articles. Delete is not implemented.",
        functions=(
            _read(
                (
                    f("document_id", "int", "Get a specific document by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a new document.",
                fields=(
                    CLIENT_ID,
                    f("document_name", "str", "Document title.", required=True),
                    f("document_content", "str", "Document content (HTML supported).", required=True),
                    f("document_description", "str", "Brief description."),
                    f("document_folder_id", "int", "Folder ID for organization."),
                ),
            ),
            FunctionSpec(
                "update",
                "Update a document. Only provided fields are changed.",
                fields=(
                    f("document_id", "int", "ID of the document to update.", required=True),
                    CLIENT_ID,
                    f("document_name", "str", "Document title."),
                    f("document_content", "str", "Document content (HTML supported)."),
                    f("document_description", "str", "Brief description."),
                    f("document_folder_id", "int", "Folder ID for organization."),
                ),
            ),
        ),
    ),
    ModuleSpec(
        name="domains",
        purpose="Domain name management and renewal tracking. Read-only module.",
        functions=(
            _read(
                (
                    f("domain_id", "int", "Get a specific domain by ID."),
                    f("domain_name", "str", "Get a domain by exact name."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="expenses",
        purpose="Track business expenses. Read-only module; requires an all-client-scoped API key.",
        functions=(
            _read(
                (
                    f("expense_id", "int", "Get a specific expense by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                ),
                notes="Requires an API key with all-client scope.",
            ),
        ),
    ),
    ModuleSpec(
        name="invoices",
        purpose="Access invoice records. Read-only module.",
        functions=(
            _read(
                (
                    f("invoice_id", "int", "Get a specific invoice by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="invoice_items",
        purpose="Retrieve line items associated with invoices. Read-only module.",
        functions=(
            _read(
                (
                    f("invoice_id", "int", "Filter items by invoice ID."),
                    f("item_id", "int", "Get a specific line item by ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="locations",
        purpose="Manage client office/site locations. Update/delete are not implemented.",
        functions=(
            _read(
                (
                    f("location_id", "int", "Get a specific location by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a new location.",
                fields=(
                    CLIENT_ID,
                    f("location_name", "str", "Location name.", required=True),
                    f("location_description", "str", "Description."),
                    f("location_country", "str", "Country."),
                    f("location_address", "str", "Street address."),
                    f("location_city", "str", "City."),
                    f("location_state", "str", "State/province."),
                    f("location_zip", "str", "ZIP/postal code."),
                    f("location_hours", "str", "Business hours."),
                    f("location_notes", "str", "Notes."),
                    f("location_primary", "int", "Primary location flag (0 or 1). Setting 1 removes the flag from other locations for this client."),
                ),
            ),
        ),
    ),
    ModuleSpec(
        name="networks",
        purpose="Network infrastructure documentation. Read-only module.",
        functions=(
            _read(
                (
                    f("network_id", "int", "Get a specific network by ID."),
                    f("network_name", "str", "Get a network by exact name."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="payments",
        purpose="Access payment records. Read-only module; requires an all-client-scoped API key.",
        functions=(
            _read(
                (
                    f("payment_id", "int", "Get a specific payment by ID."),
                    f("payment_invoice_id", "int", "Get all payments for an invoice."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                ),
                notes="Requires an API key with all-client scope.",
            ),
        ),
    ),
    ModuleSpec(
        name="products",
        purpose="Access product/service catalog. Read-only module; requires an all-client-scoped API key.",
        functions=(
            _read(
                (
                    f("product_id", "int", "Get a specific product by ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                ),
                notes="Requires an API key with all-client scope.",
            ),
        ),
    ),
    ModuleSpec(
        name="quotes",
        purpose="Access sales quote records. Read-only module.",
        functions=(
            _read(
                (
                    f("quote_id", "int", "Get a specific quote by ID."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="software",
        purpose="Software license and application tracking. Read-only module.",
        functions=(
            _read(
                (
                    f("software_id", "int", "Get a specific software record by ID."),
                    f("software_name", "str", "Get by exact name."),
                    f("software_type", "str", "Filter by type."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
    ModuleSpec(
        name="tickets",
        purpose="Help desk and issue tracking. Update/delete are not implemented; use resolve to close.",
        functions=(
            _read(
                (
                    f("ticket_id", "int", "Get a specific ticket by ID (includes status information)."),
                    f("client_id", "int", "Filter by client ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
            FunctionSpec(
                "create",
                "Create a new ticket. Ticket number is auto-generated; source is set to 'API'.",
                fields=(
                    CLIENT_ID,
                    f("ticket_subject", "str", "Ticket subject/title.", required=True),
                    f("ticket_details", "str", "Ticket description."),
                    f("ticket_priority", "str", "Priority (Low, Medium, High). Defaults to Low."),
                    f("ticket_contact_id", "int", "Contact ID (auto-selects primary contact if omitted)."),
                    f("ticket_asset_id", "int", "Related asset ID."),
                    f("ticket_vendor_id", "int", "Escalation vendor ID."),
                    f("ticket_vendor_ticket_id", "int", "Vendor's ticket number."),
                    f("ticket_assigned_to", "int", "Assigned user ID."),
                    f("ticket_billable", "int", "Billable flag (0 or 1)."),
                ),
            ),
            FunctionSpec(
                "resolve",
                "Resolve/close a ticket. Sets status to Resolved and records the resolution timestamp.",
                fields=(f("ticket_id", "int", "ID of the ticket to resolve.", required=True),),
            ),
        ),
    ),
    ModuleSpec(
        name="vendors",
        purpose="Manage vendor/supplier records. Read-only module.",
        functions=(
            _read(
                (
                    f("vendor_id", "int", "Get a specific vendor by ID."),
                    f("limit", "int", "Max records to return (default 50).", default=50),
                    f("offset", "int", "Number of records to skip for pagination.", default=0),
                )
            ),
        ),
    ),
)


def module_names() -> tuple[str, ...]:
    return tuple(m.name for m in MODULES)


def get_module(name: str) -> ModuleSpec | None:
    for m in MODULES:
        if m.name == name:
            return m
    return None


def all_functions() -> tuple[tuple[ModuleSpec, FunctionSpec], ...]:
    out: list[tuple[ModuleSpec, FunctionSpec]] = []
    for m in MODULES:
        for fn in m.functions:
            out.append((m, fn))
    return tuple(out)
