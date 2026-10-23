# Untitled object in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy
```

New sign-in absolute/inactivity bounds; idle must not exceed absolute

| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## session_policy Type

`object` ([Details](configure-module-input-properties-session_policy.md))

# session_policy Properties

| Property                              | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                        |
| :------------------------------------ | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [absolute_seconds](#absolute_seconds) | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-session_policy-properties-absolute_seconds.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy/properties/absolute_seconds") |
| [idle_seconds](#idle_seconds)         | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-session_policy-properties-idle_seconds.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy/properties/idle_seconds")         |

## absolute_seconds



`absolute_seconds`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-session_policy-properties-absolute_seconds.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy/properties/absolute_seconds")

### absolute_seconds Type

`integer`

### absolute_seconds Constraints

**maximum**: the value of this number must smaller than or equal to: `86400`

**minimum**: the value of this number must greater than or equal to: `60`

## idle_seconds



`idle_seconds`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-session_policy-properties-idle_seconds.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy/properties/idle_seconds")

### idle_seconds Type

`integer`

### idle_seconds Constraints

**maximum**: the value of this number must smaller than or equal to: `86400`

**minimum**: the value of this number must greater than or equal to: `60`
