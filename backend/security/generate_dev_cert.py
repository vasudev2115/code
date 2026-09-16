"""
Generate a self-signed TLS certificate for local HTTPS development.

For a real deployment you'd use a CA-issued cert (Let's Encrypt is
free and standard), but for running the backend over HTTPS on your
own machine/VM during development and demos, a self-signed cert is
normal and sufficient -- your browser will show a "not trusted"
warning you click through, which is expected for self-signed certs.

This actually generates real, valid X.509 certificate files using the
`cryptography` library (not a placeholder) -- run it and check the
output files with `openssl x509 -in cert.pem -text -noout` if you want
to inspect them.

Usage:
    python generate_dev_cert.py
    # then:
    uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
"""

import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_self_signed_cert(common_name: str = "localhost", days_valid: int = 365):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name), x509.DNSName("127.0.0.1")]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    return key_pem, cert_pem


def _self_test():
    """Generates a cert, then actually parses it back and checks the fields are right."""
    key_pem, cert_pem = generate_self_signed_cert(common_name="localhost", days_valid=30)

    # Parse the generated cert back to verify it's structurally valid
    # and contains what we expect -- not just "some bytes came out."
    parsed_cert = x509.load_pem_x509_certificate(cert_pem)
    cn = parsed_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert cn == "localhost", f"expected CN=localhost, got {cn}"

    now = datetime.datetime.now(datetime.timezone.utc)
    assert parsed_cert.not_valid_before_utc <= now <= parsed_cert.not_valid_after_utc, "cert should be valid right now"

    validity_days = (parsed_cert.not_valid_after_utc - parsed_cert.not_valid_before_utc).days
    assert validity_days == 30, f"expected 30-day validity, got {validity_days}"

    # Verify the private key actually corresponds to the cert's public key
    private_key = serialization.load_pem_private_key(key_pem, password=None)
    assert private_key.public_key().public_numbers() == parsed_cert.public_key().public_numbers(), (
        "BUG: generated private key doesn't match the certificate's public key"
    )

    print(f"PASS: generated a real, structurally valid X.509 cert (CN={cn}, {validity_days} days validity)")
    print("PASS: private key correctly corresponds to the certificate's public key")
    return key_pem, cert_pem


if __name__ == "__main__":
    key_pem, cert_pem = _self_test()

    with open("key.pem", "wb") as f:
        f.write(key_pem)
    with open("cert.pem", "wb") as f:
        f.write(cert_pem)
    print("\nWrote key.pem and cert.pem to the current directory.")
    print("Run the backend over HTTPS with:")
    print("  uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem")
