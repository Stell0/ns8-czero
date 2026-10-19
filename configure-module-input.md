# configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json
```

Configure czero

| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                              |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json](czero/configure-module-input.json "open original schema") |

## configure-module input Type

`object` ([configure-module input](configure-module-input.md))

## configure-module input Examples

```json
{
  "host": "c0.example.test",
  "lets_encrypt": false
}
```

# configure-module input Properties

| Property                          | Type      | Required | Nullable       | Defined by                                                                                                                                                                |
| :-------------------------------- | :-------- | :------- | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [host](#host)                     | Merged    | Required | cannot be null | [configure-module input](configure-module-input-properties-host.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/host")                     |
| [lets_encrypt](#lets_encrypt)     | `boolean` | Optional | cannot be null | [configure-module input](configure-module-input-properties-lets_encrypt.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/lets_encrypt")     |
| [user_domain](#user_domain)       | Merged    | Optional | cannot be null | [configure-module input](configure-module-input-properties-user_domain.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/user_domain")       |
| [idp](#idp)                       | `string`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-idp.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/idp")                       |
| [owner](#owner)                   | `string`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-owner.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/owner")                   |
| [retrieval](#retrieval)           | `object`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval")           |
| [session_policy](#session_policy) | `object`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-session_policy.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy") |

## host

Application DNS hostname, without scheme or path

`host`

* is required

* Type: `string` ([Details](configure-module-input-properties-host.md))

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-host.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/host")

### host Type

`string` ([Details](configure-module-input-properties-host.md))

not

* [Untitled undefined type in configure-module input](configure-module-input-properties-host-not.md "check type definition")

### host Constraints

**maximum length**: the maximum number of characters for this string is: `253`

**minimum length**: the minimum number of characters for this string is: `3`

**pattern**: the string must match the following regular expression:&#x20;

```regexp
^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$
```

[try pattern](https://regexr.com/?expression=%5E\(%3F%3A%5BA-Za-z0-9%5D\(%3F%3A%5BA-Za-z0-9-%5D%7B0%2C61%7D%5BA-Za-z0-9%5D\)%3F%5C.\)%2B%5BA-Za-z%5D\(%3F%3A%5BA-Za-z0-9-%5D%7B0%2C61%7D%5BA-Za-z0-9%5D\)%3F%24 "try regular expression with regexr.com")

## lets_encrypt

Request a certificate through NS8 Traefik

`lets_encrypt`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-lets_encrypt.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/lets_encrypt")

### lets_encrypt Type

`boolean`

### lets_encrypt Default Value

The default value is:

```json
false
```

## user_domain



`user_domain`

* is optional

* Type: `string` ([Details](configure-module-input-properties-user_domain.md))

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-user_domain.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/user_domain")

### user_domain Type

`string` ([Details](configure-module-input-properties-user_domain.md))

not

* [Untitled undefined type in configure-module input](configure-module-input-properties-user_domain-not.md "check type definition")

### user_domain Constraints

**maximum length**: the maximum number of characters for this string is: `253`

## idp



`idp`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-idp.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/idp")

### idp Type

`string`

### idp Constraints

**maximum length**: the maximum number of characters for this string is: `36`

**pattern**: the string must match the following regular expression:&#x20;

```regexp
^$|^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$
```

[try pattern](https://regexr.com/?expression=%5E%24%7C%5E%5BA-Fa-f0-9%5D%7B8%7D-%5BA-Fa-f0-9%5D%7B4%7D-%5BA-Fa-f0-9%5D%7B4%7D-%5BA-Fa-f0-9%5D%7B4%7D-%5BA-Fa-f0-9%5D%7B12%7D%24 "try regular expression with regexr.com")

## owner



`owner`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-owner.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/owner")

### owner Type

`string`

### owner Constraints

**maximum length**: the maximum number of characters for this string is: `128`

**pattern**: the string must match the following regular expression:&#x20;

```regexp
^[A-Za-z0-9_.@-]*$
```

[try pattern](https://regexr.com/?expression=%5E%5BA-Za-z0-9_.%40-%5D*%24 "try regular expression with regexr.com")

## retrieval



`retrieval`

* is optional

* Type: `object` ([Details](configure-module-input-properties-retrieval.md))

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval")

### retrieval Type

`object` ([Details](configure-module-input-properties-retrieval.md))

## session_policy

New sign-in absolute/inactivity bounds; idle must not exceed absolute

`session_policy`

* is optional

* Type: `object` ([Details](configure-module-input-properties-session_policy.md))

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-session_policy.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/session_policy")

### session_policy Type

`object` ([Details](configure-module-input-properties-session_policy.md))
