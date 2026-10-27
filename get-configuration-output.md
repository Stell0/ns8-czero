# get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json
```

Get czero configuration

| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                  |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :------------------------------------------------------------------------------------------ |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [get-configuration-output.json](czero/get-configuration-output.json "open original schema") |

## get-configuration output Type

`object` ([get-configuration output](get-configuration-output.md))

# get-configuration output Properties

| Property                                            | Type      | Required | Nullable       | Defined by                                                                                                                                                                                        |
| :-------------------------------------------------- | :-------- | :------- | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [host](#host)                                       | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-host.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/host")                                       |
| [lets_encrypt](#lets_encrypt)                       | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-lets_encrypt.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/lets_encrypt")                       |
| [user_domain](#user_domain)                         | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-user_domain.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/user_domain")                         |
| [idp](#idp)                                         | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-idp.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/idp")                                         |
| [owner](#owner)                                     | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-owner.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner")                                     |
| [owner_ldap_uuid](#owner_ldap_uuid)                 | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-owner_ldap_uuid.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner_ldap_uuid")                 |
| [retrieval](#retrieval)                             | `object`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval")                             |
| [session_policy](#session_policy)                   | `object`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-session_policy.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy")                   |
| [cimd_enabled](#cimd_enabled)                       | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-cimd_enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/cimd_enabled")                       |
| [connection_idle_seconds](#connection_idle_seconds) | `integer` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-connection_idle_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/connection_idle_seconds") |

## host



`host`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-host.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/host")

### host Type

`string`

## lets_encrypt



`lets_encrypt`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-lets_encrypt.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/lets_encrypt")

### lets_encrypt Type

`boolean`

## user_domain



`user_domain`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-user_domain.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/user_domain")

### user_domain Type

`string`

## idp



`idp`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-idp.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/idp")

### idp Type

`string`

## owner



`owner`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-owner.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner")

### owner Type

`string`

## owner_ldap_uuid



`owner_ldap_uuid`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-owner_ldap_uuid.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner_ldap_uuid")

### owner_ldap_uuid Type

`string`

## retrieval



`retrieval`

* is required

* Type: `object` ([Details](get-configuration-output-properties-retrieval.md))

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval")

### retrieval Type

`object` ([Details](get-configuration-output-properties-retrieval.md))

## session_policy



`session_policy`

* is required

* Type: `object` ([Details](get-configuration-output-properties-session_policy.md))

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-session_policy.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/session_policy")

### session_policy Type

`object` ([Details](get-configuration-output-properties-session_policy.md))

## cimd_enabled

Allow administrator-approved public OAuth client metadata URLs; disabled by default

`cimd_enabled`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-cimd_enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/cimd_enabled")

### cimd_enabled Type

`boolean`

## connection_idle_seconds



`connection_idle_seconds`

* is required

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-connection_idle_seconds.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/connection_idle_seconds")

### connection_idle_seconds Type

`integer`

### connection_idle_seconds Constraints

**multiple of**: the value of this number must be a multiple of: `86400`

**maximum**: the value of this number must smaller than or equal to: `31536000`

**minimum**: the value of this number must greater than or equal to: `86400`
