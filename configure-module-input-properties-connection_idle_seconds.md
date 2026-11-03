# Untitled integer in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/connection_idle_seconds
```



| Abstract            | Extensible | Status         | Identifiable            | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :---------------------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | Unknown identifiability | Forbidden         | Allowed               | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## connection_idle_seconds Type

`integer`

## connection_idle_seconds Constraints

**multiple of**: the value of this number must be a multiple of: `86400`

**maximum**: the value of this number must smaller than or equal to: `31536000`

**minimum**: the value of this number must greater than or equal to: `86400`
