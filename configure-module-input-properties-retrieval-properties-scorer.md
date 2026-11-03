# Untitled object in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## scorer Type

`object` ([Details](configure-module-input-properties-retrieval-properties-scorer.md))

# scorer Properties

| Property                        | Type          | Required | Nullable       | Defined by                                                                                                                                                                                                                                            |
| :------------------------------ | :------------ | :------- | :------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [endpoint](#endpoint)           | `string`      | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-endpoint.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/endpoint")           |
| [model](#model)                 | `string`      | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-model.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/model")                 |
| [api_key](#api_key)             | `string`      | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/api_key")             |
| [clear_api_key](#clear_api_key) | `boolean`     | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-clear_api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/clear_api_key") |
| [timeout](#timeout)             | `number`      | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-timeout.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/timeout")             |
| [mode](#mode)                   | Not specified | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-mode.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/mode")                   |
| [threshold](#threshold)         | `number`      | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-threshold.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/threshold")         |

## endpoint



`endpoint`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-endpoint.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/endpoint")

### endpoint Type

`string`

### endpoint Constraints

**maximum length**: the maximum number of characters for this string is: `2048`

## model



`model`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-model.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/model")

### model Type

`string`

### model Constraints

**maximum length**: the maximum number of characters for this string is: `128`

## api_key



`api_key`

* is optional

* Type: `string`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/api_key")

### api_key Type

`string`

### api_key Constraints

**maximum length**: the maximum number of characters for this string is: `4096`

## clear_api_key



`clear_api_key`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-clear_api_key.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/clear_api_key")

### clear_api_key Type

`boolean`

## timeout



`timeout`

* is optional

* Type: `number`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-timeout.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/timeout")

### timeout Type

`number`

### timeout Constraints

**maximum**: the value of this number must smaller than or equal to: `5`

**minimum**: the value of this number must greater than or equal to: `0.05`

## mode



`mode`

* is optional

* Type: unknown

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-mode.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/mode")

### mode Type

unknown

### mode Constraints

**enum**: the value of this property must be equal to one of the following values:

| Value      | Explanation |
| :--------- | :---------- |
| `"off"`    |             |
| `"rerank"` |             |
| `"filter"` |             |

## threshold



`threshold`

* is optional

* Type: `number`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-scorer-properties-threshold.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/scorer/properties/threshold")

### threshold Type

`number`

### threshold Constraints

**maximum**: the value of this number must smaller than or equal to: `1`

**minimum**: the value of this number must greater than or equal to: `0`
