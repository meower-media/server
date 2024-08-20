from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from typing import List

class SigningKeys:
    def __init__(self, priv_bytes: bytes, pub_bytes: bytes|List[bytes]):
        self.priv_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        if isinstance(pub_bytes, bytes):
            pub_bytes = [pub_bytes]
        self.pub_keys = [
            Ed25519PublicKey.from_public_bytes(_pub_bytes)
            for _pub_bytes in pub_bytes
        ]
    
    def sign(self, data: bytes) -> bytes:
        return self.priv_key.sign(data)

    def validate(self, signature: bytes, data: bytes) -> bool:
        for pub_key in self.pub_keys:
            try:
                pub_key.verify(signature, data)
            except:
                continue
            else:
                return True
            
        return False

    def rotate(self) -> tuple[bytes, bytes]:
        new_priv = Ed25519PrivateKey.generate()
        new_pub = new_priv.public_key()

        self.priv_key = new_priv
        self.pub_keys.append(new_pub)

        return new_priv.private_bytes_raw(), new_pub.public_bytes_raw()
