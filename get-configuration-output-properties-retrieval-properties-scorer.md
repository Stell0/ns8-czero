# Untitled object in get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                    |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [get-configuration-output.json\*](czero/get-configuration-output.json "open original schema") |

## scorer Type

`object` ([Details](get-configuration-output-properties-retrieval-properties-scorer.md))

# scorer Properties

| Property                                  | Type          | Required | Nullable       | Defined by                                                                                                                                                                                                                                                            |
| :---------------------------------------- | :------------ | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [endpoint](#endpoint)                     | `string`      | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-endpoint.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/endpoint")                     |
| [model](#model)                           | `string`      | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-model.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/model")                           |
| [timeout](#timeout)                       | `number`      | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-timeout.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/timeout")                       |
| [mode](#mode)                             | Not specified | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-mode.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/mode")                             |
| [threshold](#threshold)                   | `number`      | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-threshold.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/threshold")                   |
| [api_key_configured](#api_key_configured) | `boolean`     | Required | cannot be null | [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-api_key_configured.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/api_key_configured") |

## endpoint



`endpoint`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-endpoint.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/endpoint")

### endpoint Type

`string`

### endpoint Constraints

**maximum length**: the maximum number of characters for this string is: `2048`

## model



`model`

* is required

* Type: `string`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-model.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/model")

### model Type

`string`

### model Constraints

**maximum length**: the maximum number of characters for this string is: `128`

## timeout



`timeout`

* is required

* Type: `number`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-timeout.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/timeout")

### timeout Type

`number`

### timeout Constraints

**maximum**: the value of this number must smaller than or equal to: `5`

**minimum**: the value of this number must greater than or equal to: `0.05`

## mode



`mode`

* is required

* Type: unknown

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-mode.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/mode")

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

* is required

* Type: `number`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-threshold.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/threshold")

### threshold Type

`number`

### threshold Constraints

**maximum**: the value of this number must smaller than or equal to: `1`

**minimum**: the value of this number must greater than or equal to: `0`

## api_key_configured



`api_key_configured`

* is required

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-retrieval-properties-scorer-properties-api_key_configured.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/retrieval/properties/scorer/properties/api_key_configured")

### api_key_configured Type

`boolean`
