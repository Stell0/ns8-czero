# Untitled object in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## limits Type

`object` ([Details](configure-module-input-properties-retrieval-properties-limits.md))

# limits Properties

| Property                                | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                                                    |
| :-------------------------------------- | :-------- | :------- | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [max_limit](#max_limit)                 | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-max_limit.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/max_limit")                 |
| [candidates](#candidates)               | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-candidates.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/candidates")               |
| [graph_depth](#graph_depth)             | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-graph_depth.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/graph_depth")             |
| [scorer_candidates](#scorer_candidates) | `integer` | Optional | cannot be null | [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-scorer_candidates.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/scorer_candidates") |

## max_limit



`max_limit`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-max_limit.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/max_limit")

### max_limit Type

`integer`

### max_limit Constraints

**maximum**: the value of this number must smaller than or equal to: `50`

**minimum**: the value of this number must greater than or equal to: `1`

## candidates



`candidates`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-candidates.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/candidates")

### candidates Type

`integer`

### candidates Constraints

**maximum**: the value of this number must smaller than or equal to: `64`

**minimum**: the value of this number must greater than or equal to: `1`

## graph_depth



`graph_depth`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-graph_depth.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/graph_depth")

### graph_depth Type

`integer`

### graph_depth Constraints

**maximum**: the value of this number must smaller than or equal to: `3`

**minimum**: the value of this number must greater than or equal to: `0`

## scorer_candidates



`scorer_candidates`

* is optional

* Type: `integer`

* cannot be null

* defined in: [configure-module input](configure-module-input-properties-retrieval-properties-limits-properties-scorer_candidates.md "http://schema.nethserver.org/czero/configure-module-input.json#/properties/retrieval/properties/limits/properties/scorer_candidates")

### scorer_candidates Type

`integer`

### scorer_candidates Constraints

**maximum**: the value of this number must smaller than or equal to: `16`

**minimum**: the value of this number must greater than or equal to: `1`
