Unofficial [Warframe Market](https://warframe.market) command-line utility.

```
usage: wfmk.py [-h] [-d DEBUG] [-q] [-v] [--clear-cache | -l | -O | -s]
               [-C DIR] [--no-cache] [--ttl-items CACHE_TTL]
               [--ttl-orders CACHE_TTL] [--rate-limit RATE_LIMIT] [-a] [-b]
               [-f FILE] [-P {pc,ps4,switch,xbox}] [-L LANGUAGE] [-r]
               [item [item ...]]

Look up information about Warframe items on warframe.market

positional arguments:
  item                  Item(s) to look up. Items are not case-sensitive and
                        may contain the wildcards *, ?, and [] (which behave
                        like bash).

optional arguments:
  -h, --help            show this help message and exit
  -d DEBUG, --debug DEBUG
                        Set the debug messaging level.
  -q, --quiet           Print fewer messages.
  -v, --verbose         Print more verbose messages about what is happening.
                        Can be specified multiple times.

Actions:
  --clear-cache         Delete the contents of the local disk cache
  -l, --list            List items matching the specified name patterns
  -O, --orders          List an item's current orders (the default)
  -s, --summary         Show only a summary of the item's prices

Cache Options:
  -C DIR, --cache-dir DIR
                        The directory to use for the local disk cache.
                        Default: /home/tim/.cache/warframe-market
  --no-cache            Disable the local disk cache
  --ttl-items CACHE_TTL
                        How long to cache the list of all Warframe items.
                        Default: 1d
  --ttl-orders CACHE_TTL
                        How long to cache the list of orders for an item.
                        Default: 10m
  --rate-limit RATE_LIMIT
                        How fast to send API requests (per minute). Default:
                        180

Miscellaneous Options:
  -a, --all             Show all matching users (show more than the top 5
                        users)
  -b, --buyers          Show only users looking to buy the item
  -f FILE, --file FILE  Read list of items from a file, one item per line.
  -P {pc,ps4,switch,xbox}, --platform {pc,ps4,switch,xbox}
                        The Warframe platform to search. Default: pc.
  -L LANGUAGE, --language LANGUAGE
                        The Warframe language code to search. Default: en.
                        E.g. "de", "en", "fr", "ko", "ru", "sv", or "zh"
  -r, --reverse         Reverse the sorting order

Examples:
# Print the current selling price for the Ammo Drum Mod
    wfmk.py "ammo drum"

# Print the buying price for all Ember Prime items (and set)
    wfmk.py -s -b "Ember Prime*"

# List all items with "rubedo" in their name:
    wfmk.py -l "*rubedo*"

# List all Xiphos parts, but not the set
    wfmk.py -l "xiphos [a-f]*"
    wfmk.py -l "xiphos [!s]*"

# NOTE: All item matches are case insensitive and follow Python
#       fnmatch rules.
```
