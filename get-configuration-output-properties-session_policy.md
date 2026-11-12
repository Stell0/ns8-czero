# Untitled object in get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                    |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [get-configuration-output.json\*](czero/get-configuration-output.json "open original schema") |

## session_policy Type

`object` ([Details](get-configuration-output-properties-session_policy.md))

# session_policy Properties

| Property                              | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                              |
| :------------------------------------ | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [absolute_seconds](#absolute_seconds) | `integer` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-session_policy-properties-absolute_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy/properties/absolute_seconds") |
| [idle_seconds](#idle_seconds)         | `integer` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-session_policy-properties-idle_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy/properties/idle_seconds")         |

## absolute_seconds



`absolute_seconds`

* is required

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-session_policy-properties-absolute_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy/properties/absolute_seconds")

### absolute_seconds Type

`integer`

### absolute_seconds Constraints

**maximum**: the value of this number must smaller than or equal to: `86400`

**minimum**: the value of this number must greater than or equal to: `60`

## idle_seconds



`idle_seconds`

* is required

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-session_policy-properties-idle_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy/properties/idle_seconds")

### idle_seconds Type

`integer`

### idle_seconds Constraints

**maximum**: the value of this number must smaller than or equal to: `86400`

**minimum**: the value of this number must greater than or equal to: `60`
