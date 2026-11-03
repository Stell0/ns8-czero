# Untitled object in get-configuration output Schema

```txt
http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction
```



| Abstract            | Extensible | Status         | Identifiable | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                    |
| :------------------ | :--------- | :------------- | :----------- | :---------------- | :-------------------- | :------------------ | :-------------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | No           | Forbidden         | Forbidden             | none                | [get-configuration-output.json\*](czero/get-configuration-output.json "open original schema") |

## extraction Type

`object` ([Details](get-configuration-output-properties-extraction.md))

# extraction Properties

| Property                                | Type      | Required | Nullable       | Defined by                                                                                                                                                                                                                        |
| :-------------------------------------- | :-------- | :------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [enabled](#enabled)                     | `boolean` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/enabled")                     |
| [workers](#workers)                     | `integer` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/workers")                     |
| [document_workers](#document_workers)   | `integer` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-document_workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/document_workers")   |
| [space_workers](#space_workers)         | `integer` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-space_workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/space_workers")         |
| [max_queued_units](#max_queued_units)   | `integer` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-max_queued_units.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/max_queued_units")   |
| [max_staging_bytes](#max_staging_bytes) | `integer` | Optional | cannot be null | [get-configuration output](get-configuration-output-properties-extraction-properties-max_staging_bytes.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/max_staging_bytes") |

## enabled



`enabled`

* is optional

* Type: `boolean`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-enabled.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/enabled")

### enabled Type

`boolean`

## workers



`workers`

* is optional

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/workers")

### workers Type

`integer`

### workers Constraints

**maximum**: the value of this number must smaller than or equal to: `4`

**minimum**: the value of this number must greater than or equal to: `1`

## document_workers



`document_workers`

* is optional

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-document_workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/document_workers")

### document_workers Type

`integer`

### document_workers Constraints

**maximum**: the value of this number must smaller than or equal to: `4`

**minimum**: the value of this number must greater than or equal to: `1`

## space_workers



`space_workers`

* is optional

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-space_workers.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/space_workers")

### space_workers Type

`integer`

### space_workers Constraints

**maximum**: the value of this number must smaller than or equal to: `4`

**minimum**: the value of this number must greater than or equal to: `1`

## max_queued_units



`max_queued_units`

* is optional

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-max_queued_units.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/max_queued_units")

### max_queued_units Type

`integer`

### max_queued_units Constraints

**maximum**: the value of this number must smaller than or equal to: `4000`

**minimum**: the value of this number must greater than or equal to: `200`

## max_staging_bytes



`max_staging_bytes`

* is optional

* Type: `integer`

* cannot be null

* defined in: [get-configuration output](get-configuration-output-properties-extraction-properties-max_staging_bytes.md "http://schema.nethserver.org/czero/get-configuration-output.json#/properties/extraction/properties/max_staging_bytes")

### max_staging_bytes Type

`integer`

### max_staging_bytes Constraints

**maximum**: the value of this number must smaller than or equal to: `67108864`

**minimum**: the value of this number must greater than or equal to: `2097152`
