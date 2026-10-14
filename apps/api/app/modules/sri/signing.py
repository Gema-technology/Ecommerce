"""XAdES-BES signing for comprobantes electrónicos SRI (PKCS#12)."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import Certificate
from lxml import etree

NSMAP = {
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
}


def load_pkcs12(cert_path: Path | str, password: str) -> tuple[object, Certificate, list[Certificate]]:
    data = Path(cert_path).read_bytes()
    private_key, certificate, additional = pkcs12.load_key_and_certificates(
        data,
        password.encode("utf-8") if password else None,
    )
    if private_key is None or certificate is None:
        raise ValueError("Invalid PKCS#12: missing private key or certificate")
    return private_key, certificate, list(additional or [])


def cert_digest_sha1(certificate: Certificate) -> bytes:
    return hashlib.sha1(certificate.public_bytes(serialization.Encoding.DER)).digest()


def _c14n(node: etree._Element) -> bytes:
    return etree.tostring(node, method="c14n", exclusive=False, with_comments=False)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def sign_comprobante_xml(xml_text: str, cert_path: Path | str, password: str) -> str:
    """
    Attach an enveloped XAdES-BES signature to the root comprobante element.
    Compatible with SRI recepción offline (RSA-SHA1 / SHA1 digests).
    """
    private_key, certificate, _extra = load_pkcs12(cert_path, password)
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(xml_text.encode("utf-8"), parser=parser)

    signature_id = "Signature"
    signed_props_id = "SignedProperties"
    reference_uri = "#" + (root.get("id") or root.get("Id") or "comprobante")
    # Ensure id attribute present for reference
    if root.get("id") is None and root.get("Id") is None:
        root.set("id", "comprobante")
        reference_uri = "#comprobante"

    ds = NSMAP["ds"]
    xades = NSMAP["xades"]

    signature = etree.Element(f"{{{ds}}}Signature", nsmap={"ds": ds, "xades": xades})
    signature.set("Id", signature_id)
    signed_info = etree.SubElement(signature, f"{{{ds}}}SignedInfo")
    c14n_method = etree.SubElement(signed_info, f"{{{ds}}}CanonicalizationMethod")
    c14n_method.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    sig_method = etree.SubElement(signed_info, f"{{{ds}}}SignatureMethod")
    sig_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#rsa-sha1")

    # Reference to document
    ref_doc = etree.SubElement(signed_info, f"{{{ds}}}Reference")
    ref_doc.set("Id", "Reference-comprobante")
    ref_doc.set("URI", reference_uri)
    transforms = etree.SubElement(ref_doc, f"{{{ds}}}Transforms")
    t1 = etree.SubElement(transforms, f"{{{ds}}}Transform")
    t1.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature")
    t2 = etree.SubElement(transforms, f"{{{ds}}}Transform")
    t2.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    digest_method = etree.SubElement(ref_doc, f"{{{ds}}}DigestMethod")
    digest_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")
    digest_value = etree.SubElement(ref_doc, f"{{{ds}}}DigestValue")

    # Temporary attach signature shell to compute document digest excluding signature
    root.append(signature)
    # Document digest: clone without Signature
    clone = etree.fromstring(etree.tostring(root))
    for sig in clone.xpath("//*[local-name()='Signature']"):
        parent = sig.getparent()
        if parent is not None:
            parent.remove(sig)
    doc_c14n = _c14n(clone)
    digest_value.text = _b64(hashlib.sha1(doc_c14n).digest())

    # Object / SignedProperties
    obj = etree.SubElement(signature, f"{{{ds}}}Object")
    qualifying = etree.SubElement(obj, f"{{{xades}}}QualifyingProperties")
    qualifying.set("Target", f"#{signature_id}")
    signed_props = etree.SubElement(qualifying, f"{{{xades}}}SignedProperties")
    signed_props.set("Id", signed_props_id)

    signed_sig_props = etree.SubElement(signed_props, f"{{{xades}}}SignedSignatureProperties")
    signing_time = etree.SubElement(signed_sig_props, f"{{{xades}}}SigningTime")
    signing_time.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    signing_cert = etree.SubElement(signed_sig_props, f"{{{xades}}}SigningCertificate")
    cert_el = etree.SubElement(signing_cert, f"{{{xades}}}Cert")
    cert_digest = etree.SubElement(cert_el, f"{{{xades}}}CertDigest")
    dm = etree.SubElement(cert_digest, f"{{{ds}}}DigestMethod")
    dm.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")
    dv = etree.SubElement(cert_digest, f"{{{ds}}}DigestValue")
    dv.text = _b64(cert_digest_sha1(certificate))
    issuer_serial = etree.SubElement(cert_el, f"{{{xades}}}IssuerSerial")
    issuer_name = etree.SubElement(issuer_serial, f"{{{ds}}}X509IssuerName")
    issuer_name.text = certificate.issuer.rfc4514_string()
    serial = etree.SubElement(issuer_serial, f"{{{ds}}}X509SerialNumber")
    serial.text = str(certificate.serial_number)

    # Reference to SignedProperties
    ref_props = etree.SubElement(signed_info, f"{{{ds}}}Reference")
    ref_props.set("Id", "SignedProperties-Reference")
    ref_props.set("Type", "http://uri.etsi.org/01903#SignedProperties")
    ref_props.set("URI", f"#{signed_props_id}")
    dm2 = etree.SubElement(ref_props, f"{{{ds}}}DigestMethod")
    dm2.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")
    dv2 = etree.SubElement(ref_props, f"{{{ds}}}DigestValue")
    props_c14n = _c14n(signed_props)
    dv2.text = _b64(hashlib.sha1(props_c14n).digest())

    # SignatureValue over SignedInfo
    signed_info_c14n = _c14n(signed_info)
    signature_bytes = private_key.sign(  # type: ignore[union-attr]
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1(),
    )
    sig_value = etree.SubElement(signature, f"{{{ds}}}SignatureValue")
    sig_value.set("Id", "SignatureValue")
    sig_value.text = _b64(signature_bytes)

    # KeyInfo
    key_info = etree.SubElement(signature, f"{{{ds}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{ds}}}X509Data")
    x509_cert = etree.SubElement(x509_data, f"{{{ds}}}X509Certificate")
    x509_cert.text = _b64(certificate.public_bytes(serialization.Encoding.DER))

    # Move Object after SignatureValue/KeyInfo order expected by some validators
    # Current order: SignedInfo, Object, SignatureValue, KeyInfo — reorder
    signature.remove(obj)
    signature.append(obj)

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,
    ).decode("utf-8")


def verify_cert_loadable(cert_path: Path | str, password: str) -> dict[str, str]:
    """Smoke-test certificate; returns subject / not_after for UI."""
    _key, certificate, _ = load_pkcs12(cert_path, password)
    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "not_valid_after": certificate.not_valid_after_utc.isoformat(),
        "serial": str(certificate.serial_number),
    }
