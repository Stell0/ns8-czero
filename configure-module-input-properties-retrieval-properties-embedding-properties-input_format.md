# Untitled string in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/embedding/properties/input_format
```

Embedding input format; context-v1 requires building a separate complete index.

| Abstract            | Extensible | Status         | Identifiable            | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :---------------------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | Unknown identifiability | Forbidden         | Allowed               | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## input_format Type

`string`

## input_format Constraints

**enum**: the value of this property must be equal to one of the following values:

| Value          | Explanation |    |    |
| :------------- | :---------- | :- | :- |
| `"legacy"`     |             |
| `"context-v1"` |             |
