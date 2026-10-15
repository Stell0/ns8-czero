# Untitled object in get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                    |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [get-configuration-output.json\*](czero/get-configuration-output.json "open original schema") |

## embedding Type

`object` ([Details](get-configuration-output-properties-retrieval-properties-embedding.md))

# embedding Properties

| Property                                  | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                                                                  |
| :---------------------------------------- | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [endpoint](#endpoint)                     | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-endpoint.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/endpoint")                     |
| [model](#model)                           | `string`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-model.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/model")                           |
| [timeout](#timeout)                       | `number`  | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-timeout.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/timeout")                       |
| [enabled](#enabled)                       | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/enabled")                       |
| [dimensions](#dimensions)                 | `integer` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-dimensions.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/dimensions")                 |
| [send_dimensions](#send_dimensions)       | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-send_dimensions.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/send_dimensions")       |
| [api_key_configured](#api_key_configured) | `boolean` | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-api_key_configured.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/api_key_configured") |

## endpoint



`endpoint`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-endpoint.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/endpoint")

### endpoint Type

`string`

### endpoint Constraints

**maximum length**: the maximum number of characters for this string is: `2048`

## model



`model`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-model.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/model")

### model Type

`string`

### model Constraints

**maximum length**: the maximum number of characters for this string is: `128`

## timeout



`timeout`

* is required

* Type: `number`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-timeout.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/timeout")

### timeout Type

`number`

### timeout Constraints

**maximum**: the value of this number must smaller than or equal to: `5`

**minimum**: the value of this number must greater than or equal to: `0.05`

## enabled



`enabled`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/enabled")

### enabled Type

`boolean`

## dimensions



`dimensions`

* is required

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-dimensions.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/dimensions")

### dimensions Type

`integer`

### dimensions Constraints

**maximum**: the value of this number must smaller than or equal to: `2000`

**minimum**: the value of this number must greater than or equal to: `1`

## send_dimensions



`send_dimensions`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-send_dimensions.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/send_dimensions")

### send_dimensions Type

`boolean`

## api_key_configured



`api_key_configured`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-embedding-properties-api_key_configured.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/embedding/properties/api_key_configured")

### api_key_configured Type

`boolean`
