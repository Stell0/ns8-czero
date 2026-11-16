# Untitled object in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## personal_data Type

`object` ([Details](configure-module-input-properties-personal_data.md))

# personal_data Properties

| Property                | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                        |
| :---------------------- | :-------- | :------- | :------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [enabled](#enabled)     | `boolean` | Required | cannot be null | [configure-module input](configure-module-input-properties-personal_data-properties-enabled.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/enabled")     |
| [nethvoice](#nethvoice) | `string`  | Optional | can be null    | [configure-module input](configure-module-input-properties-personal_data-properties-nethvoice.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/nethvoice") |
| [webtop](#webtop)       | `string`  | Optional | can be null    | [configure-module input](configure-module-input-properties-personal_data-properties-webtop.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/webtop")       |

## enabled



`enabled`

* is required

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-personal_data-properties-enabled.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/enabled")

### enabled Type

`boolean`

### enabled Default Value

The default value is:

```json
false
```

## nethvoice



`nethvoice`

* is optional

* Type: `string`

* can be null

* defined in: [configure-module input](configure-module-input-properties-personal_data-properties-nethvoice.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/nethvoice")

### nethvoice Type

`string`

### nethvoice Constraints

**UUID**: the string must be a UUID, according to [RFC 4122](https://tools.ietf.org/html/rfc4122 "check the specification")

## webtop



`webtop`

* is optional

* Type: `string`

* can be null

* defined in: [configure-module input](configure-module-input-properties-personal_data-properties-webtop.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/personal_data/properties/webtop")

### webtop Type

`string`

### webtop Constraints

**UUID**: the string must be a UUID, according to [RFC 4122](https://tools.ietf.org/html/rfc4122 "check the specification")
