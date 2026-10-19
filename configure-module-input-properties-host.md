# Untitled string in configure-module input Schema

```txt
http://schema.nethserver.org/czero/configure-module-input.json#/properties/host
```

Application DNS hostname, without scheme or path

| Abstract            | Extensible | Status         | Identifiable            | Custom Properties | Additional Properties | Access Restrictions | Defined In                                                                                |
| :------------------ | :--------- | :------------- | :---------------------- | :---------------- | :-------------------- | :------------------ | :---------------------------------------------------------------------------------------- |
| Can be instantiated | No         | Unknown status | Unknown identifiability | Forbidden         | Allowed               | none                | [configure-module-input.json\*](czero/configure-module-input.json "open original schema") |

## host Type

`string` ([Details](configure-module-input-properties-host.md))

not

* [Untitled undefined type in configure-module input](configure-module-input-properties-host-not.md "check type definition")

## host Constraints

**maximum length**: the maximum number of characters for this string is: `253`

**minimum length**: the minimum number of characters for this string is: `3`

**pattern**: the string must match the following regular expression:&#x20;

```regexp
^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$
```

[try pattern](https://regexr.com/?expression=%5E\(%3F%3A%5BA-Za-z0-9%5D\(%3F%3A%5BA-Za-z0-9-%5D%7B0%2C61%7D%5BA-Za-z0-9%5D\)%3F%5C.\)%2B%5BA-Za-z%5D\(%3F%3A%5BA-Za-z0-9-%5D%7B0%2C61%7D%5BA-Za-z0-9%5D\)%3F%24 "try regular expression with regexr.com")
