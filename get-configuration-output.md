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

| Property                            | Type      | Required | Nullable       | Defined by                                                                                                                                                                        |
| :---------------------------------- | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [host](#host)                       | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-host.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/host")                       |
| [lets_encrypt](#lets_encrypt)       | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-lets_encrypt.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/lets_encrypt")       |
| [user_domain](#user_domain)         | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-user_domain.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/user_domain")         |
| [idp](#idp)                         | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-idp.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/idp")                         |
| [owner](#owner)                     | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-owner.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner")                     |
| [owner_ldap_uuid](#owner_ldap_uuid) | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-owner_ldap_uuid.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/owner_ldap_uuid") |

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
