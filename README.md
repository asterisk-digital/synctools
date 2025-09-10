# synctools

A set of tools useful for syncing data.

## Setup

This is typically used as a submodule, which can be added to a python project as follows:

```(bash)
git submodule add git@github.com:asterisk-digital/synctools.git ./src/synctools
```

This will put synctools in the src/synctools folder of the project, which can then be imported as a module.

The library can be used as follows:

## Usage

```(python)
import synctools

synctools.utils.complete_dicts(...)
```
