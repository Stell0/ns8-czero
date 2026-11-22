# Untitled integer in get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy/properties/idle_seconds
```



| Abstract            | Extensible | Status         | Identifiable            | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                    |
| :------------------ | :--------- | :------------- | :---------------------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | Unknown identifiability | Forbidden         | Allowed               | none                | [get-configuration-output.json\*](czero/get-configuration-output.json "open original schema") |

## idle_seconds Type

`integer`

## idle_seconds Constraints

**maximum**: the value of this number must smaller than or equal to: `86400`

**minimum**: the value of this number must greater than or equal to: `60`
