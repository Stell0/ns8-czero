# Untitled object in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## embedding Type

`object` ([Details](configure-module-input-properties-retrieval-properties-embedding.md))

# embedding Properties

| Property                            | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                                                      |
| :---------------------------------- | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [endpoint](#endpoint)               | `string`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-endpoint.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/endpoint")               |
| [model](#model)                     | `string`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-model.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/model")                     |
| [api_key](#api_key)                 | `string`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/api_key")                 |
| [clear_api_key](#clear_api_key)     | `boolean` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-clear_api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/clear_api_key")     |
| [timeout](#timeout)                 | `number`  | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-timeout.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/timeout")                 |
| [enabled](#enabled)                 | `boolean` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-enabled.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/enabled")                 |
| [dimensions](#dimensions)           | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-dimensions.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/dimensions")           |
| [send_dimensions](#send_dimensions) | `boolean` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-send_dimensions.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/send_dimensions") |

## endpoint



`endpoint`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-endpoint.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/endpoint")

### endpoint Type

`string`

### endpoint Constraints

**maximum length**: the maximum number of characters for this string is: `2048`

## model



`model`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-model.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/model")

### model Type

`string`

### model Constraints

**maximum length**: the maximum number of characters for this string is: `128`

## api_key



`api_key`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/api_key")

### api_key Type

`string`

### api_key Constraints

**maximum length**: the maximum number of characters for this string is: `4096`

## clear_api_key



`clear_api_key`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-clear_api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/clear_api_key")

### clear_api_key Type

`boolean`

## timeout



`timeout`

* is optional

* Type: `number`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-timeout.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/timeout")

### timeout Type

`number`

### timeout Constraints

**maximum**: the value of this number must smaller than or equal to: `5`

**minimum**: the value of this number must greater than or equal to: `0.05`

## enabled



`enabled`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-enabled.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/enabled")

### enabled Type

`boolean`

## dimensions



`dimensions`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-dimensions.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/dimensions")

### dimensions Type

`integer`

### dimensions Constraints

**maximum**: the value of this number must smaller than or equal to: `2000`

**minimum**: the value of this number must greater than or equal to: `1`

## send_dimensions



`send_dimensions`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-embedding-properties-send_dimensions.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/send_dimensions")

### send_dimensions Type

`boolean`
