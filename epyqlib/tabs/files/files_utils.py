import json
import os
from base64 import b64decode


def ensure_dir(dir_name: str):
    if os.path.exists(dir_name):
        if os.path.isdir(dir_name):
            return
        else:
            raise NotADirectoryError(
                f"Files cache dir {dir_name} already exists but is not a directory"
            )

    os.makedirs(dir_name, exist_ok=True)


def decode(s: str) -> str:
    # Add missing padding just in case
    return json.loads(b64decode(s + "==="))


def decode_jwt(jwt: str) -> dict:
    [header, payload, signature] = jwt.split(".")
    return {
        "header": decode(header),
        "payload": decode(payload),
        "signature": signature,
    }


# jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImp0aSI6IjJiZTgxYmEwLThiMWYtNGMyMC04NWI2LWUwMGU0NThiNzM4OCIsImlhdCI6MTU1NDIzMDg4MCwiZXhwIjoxNTU0MjM0NDgwfQ.pzquCfp7SGuh9ZG3w-Opp6pCFCGIMshIh97yIB8oIow"
# print(json.dumps(decode_jwt(jwt), indent=4))
