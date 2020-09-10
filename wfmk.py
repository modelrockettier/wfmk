#!/usr/bin/python3

# On Debian/Ubuntu, you'll need to install the following packages:
#   python3-appdirs python3-prettytable python3-requests
# Or with pip, run:
#   pip install -r requirements.txt
#
# NOTE: Requires Python 3.5+

from datetime import datetime, timedelta
from prettytable import PrettyTable
import appdirs
import argparse
import errno
import fnmatch
import json
import os
import re
import requests
import statistics
import time


cache_dir = appdirs.user_cache_dir("warframe-market", False)
verbose = 0


def _nr_init(pattern, repl):
    return (re.compile("\\b" + pattern + "\\b", re.IGNORECASE), repl)


# You can use these abbreviations in a name (must be standalone words), e.g:
#   trinity p bp  -> Trinity Prime Blueprint
#   banshee?p?set -> Banshee Prime Set
#   trin*neur     -> Trinity Prime Neuroptics
#   brat*brl      -> Braton Prime Barrel
#   *scul         -> (lists all sculptures)
name_replacements = [
    _nr_init('brl',     'Barrel'),
    _nr_init('bld',     'Blade'),
    _nr_init('bp',      'Blueprint'),
    _nr_init('cara?',   'Carapace'),
    _nr_init('cere?',   'Cerebrum'),
    _nr_init('chas?s?', 'Chassis'),
    _nr_init('gtl?t?',  'Gauntlet'),
    _nr_init('hn?dl',   'Handle'),
    _nr_init('neur?',   'Neuroptics'),
    _nr_init('p',       'Prime'),
    _nr_init('rec',     'Receiver'),
    _nr_init('scul?',   'Sculpture'),
    _nr_init('stk',     'Stock'),
    _nr_init('str',     'String'),
    _nr_init('sys',     'Systems'),
]


last_request = None


def ThrottleRequests():
    global last_request
    now = datetime.now()
    if last_request:
        time_left = last_request + request_delay - now
        seconds_left = time_left / timedelta(seconds=1)
        # This request is too soon after the last request, sleep until
        # request_delay has elapsed since the last request.
        # Don't bother if we'd sleep for < 0.5 ms.
        if seconds_left >= 0.0005:
            if verbose & 2:
                print("Delaying request for {} ms".format(
                    round(seconds_left * 1000, 1)))
            time.sleep(seconds_left)
            now = datetime.now()

    last_request = now


# Download a URL and return its JSON data (on error, print a message and quit)
def DownloadJSON(session, url, desc):
    if verbose & 2:
        print("Fetching", url)

    ThrottleRequests()

    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except requests.exceptions.Timeout as err:
        print("Timeout failure retrieving", desc)
        print(err)
        quit(1)
    except requests.exceptions.ConnectionError as err:
        print("Connect error retrieving", desc)
        print(err)
        quit(1)
    except requests.exceptions.TooManyRedirects as err:
        print("Too many redirects retrieving", desc)
        quit(1)
    except requests.exceptions.HTTPError as err:
        print("HTTP error retrieving", err)
        print(err)
        quit(1)
    except requests.exceptions.RequestException as err:
        print("Request error retrieving", desc)
        print(err)
        quit(1)

    try:
        data = r.json()
    except ValueError as err:
        print("JSON decode failure with", desc)
        print(err)
        quit(1)

    if 'error' in data:
        print("API error with {}: {}".format(desc, data['error']))
        quit(1)

    return data


# Retrieve a URL (with caching support)
def GetData(session, cache_file, url, desc, cache_ttl):
    if cache_ttl is None:
        use_cache = False
    else:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        if not os.path.isdir(cache_dir):
            raise OSError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), cache_dir)

        cache_file = "{}/{}-{}-{}.json".format(cache_dir, cache_file,
                                               args.platform, args.language)
        use_cache = os.path.exists(cache_file)
        if use_cache:
            expire_time = datetime.now() - cache_ttl
            mtime = os.path.getmtime(cache_file)
            use_cache = datetime.fromtimestamp(mtime) > expire_time

    if use_cache:
        if verbose & 1:
            print("Loading {} from cache".format(desc))

        with open(cache_file, "r") as f:
            data = json.load(f)

    else:
        if verbose & 1:
            print("Fetching {}".format(desc))

        data = DownloadJSON(session, url, desc)

        if cache_ttl is not None:
            if verbose & 2:
                print("Updating {} cache".format(desc))

            with open(cache_file, "w") as f:
                json.dump(data, f)

    return data


# Clear the local file cache
def ClearCache():
    if not os.path.exists(cache_dir):
        return True

    if not os.path.isdir(cache_dir):
        raise OSError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), cache_dir)

    empty = True

    with os.scandir(cache_dir) as cache_files:
        for entry in cache_files:
            if entry.is_file():
                os.remove(entry.path)
            else:
                empty = False

    if empty:
        os.rmdir(cache_dir)
        return True
    else:
        print("Warning: Cache dir not empty\n")
        return False


# Retrieve the list of all available Warframe items
def GetAllItems(session, ttl):
    cache_file = "all_items"
    url = "https://api.warframe.market/v1/items"
    desc = "all items"
    data = GetData(session, cache_file, url, desc, ttl)

    if verbose & 4:
        print("All items:\n", json.dumps(data, indent=4))

    # Sort all items (once) so that we don't have to sort matches later
    items = data['payload']['items']
    items.sort(key=lambda x: x['item_name'])

    return items


# Retrieve an item's orders
def GetItemOrders(session, ttl, all_items, item_name):
    item = None
    for i in all_items:
        if i['item_name'] == item_name:
            item = i
            break

    if item is None:
        raise NameError("Item `" + item_name + "' not found.")

    base_url = "https://api.warframe.market/v1/items/{}/orders"
    url = base_url.format(item['url_name'])

    cache_file = "{}-orders".format(item['url_name'])
    desc = "orders for `{}'".format(item_name)

    data = GetData(session, cache_file, url, desc, ttl)

    if verbose & 8:
        print("Orders for `{}':\n".format(item_name))
        print(json.dumps(data, indent=4))

    return data['payload']['orders']


def _FindMatchingItems(item_name, all_items):
    matches = []
    regex = fnmatch.translate(item_name)
    pattern = re.compile(regex, re.IGNORECASE)
    for i in all_items:
        if pattern.match(i['item_name']) is not None:
            matches.append(i['item_name'])
    return matches


# Find items from all_items that match the item_name pattern
def FindMatchingItems(item_name, all_items):
    matches = _FindMatchingItems(item_name, all_items)
    # If there were no matches, check if the name was abbreviated
    if not matches:
        for r in name_replacements:
            item_name = r[0].sub(r[1], item_name)
        matches = _FindMatchingItems(item_name, all_items)
    return matches


# Filter out sell orders
def FilterBuyers(order):
    if order['order_type'] != 'buy':
        return False
    else:
        return FilterUsers(order)


# Filter out buy orders
def FilterSellers(order):
    if order['order_type'] != 'sell':
        return False
    else:
        return FilterUsers(order)


# Filter out offline users and console users
def FilterUsers(order):
    if order['user']['status'] == "offline":
        return False
    elif order['platform'] != args.platform:
        return False
    elif order['region'] != args.language:
        return False
    else:
        return True


# If data has 5 or more elements, remove the min and max values
def NoMinMax(data):
    data = list(data)

    if len(data) > 5:
        data.remove(min(data))
        data.remove(max(data))

    return data


# Returns the price from an order
def GetPrice(order):
    return order['platinum']


# Add a row summarizing an item's orders to the table
def AddItemSummary(t, name, orders):
    count = len(orders)

    # Item, Min, Avg5, Max, StDev5, Count
    row = [name, "N/A", "N/A", "N/A", "N/A", count]

    if count > 0:
        prices = [GetPrice(o) for o in orders]

        # The lowest priced order
        row[1] = min(prices)
        # The average of the top 5 orders
        row[2] = round(statistics.mean(prices[:5]))
        # The highest priced order
        row[3] = max(prices)
        # Standard deviation of the orders (requires at least 2 orders)
        if count > 1:
            row[4] = round(statistics.stdev(prices[:5]))

    t.add_row(row)


# Converts a string to a timedelta object (e.g. 1d or 24h or 1440m or 86400)
def StrToTimeDelta(time_str):
    if not time_str:
        return None

    match = re.match(r'^((?P<days>\d+?)d|(?P<hours>\d+?)h|(?P<minutes>\d+?)m'
                     r'|(?P<seconds>\d+?)s?)$', time_str)
    if not match:
        return None

    parts = match.groupdict()
    time_params = {k: int(v) for k, v in parts.items() if v}

    return timedelta(**time_params)


# Read the contents of a file into a list with each line becoming a separate
# item in the list
def ReadItemsFile(filename):
    lines = []
    with open(filename, 'r') as f:
        lines = f.read().splitlines()

    return lines


# Main code
retval = 0

epilog = """Examples:
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
"""

parser = argparse.ArgumentParser(
    description="Look up information about Warframe items on warframe.market",
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument(
    'items', metavar='item', nargs='*',
    help="Item(s) to look up. Items are not case-sensitive and may "
         "contain the wildcards *, ?, and [] (which behave like bash).")
parser.add_argument(
    '-d', '--debug', type=int,
    help="Set the debug messaging level.")
parser.add_argument(
    '-q', '--quiet', action="count", default=0,
    help="Print fewer messages.")
parser.add_argument(
    '-v', '--verbose', action="count", default=0,
    help="Print more verbose messages about what is happening. "
         "Can be specified multiple times.")

actions = parser.add_argument_group('Actions').add_mutually_exclusive_group()
actions.add_argument(
    '--clear-cache', action="store_true",
    help="Delete the contents of the local disk cache")
actions.add_argument(
    '-l', '--list', action="store_true",
    help="List items matching the specified name patterns")
# NOTE: Orders is the default action if none are specified.
actions.add_argument(
    '-O', '--orders', action="store_true",
    help="List an item's current orders (the default)")
actions.add_argument(
    '-s', '--summary', action="store_true",
    help="Show only a summary of the item's prices")

group = parser.add_argument_group('Cache Options')
group.add_argument(
    '-C', '--cache-dir', metavar="DIR", default=cache_dir,
    help="The directory to use for the local disk cache. "
         "Default: %(default)s")
group.add_argument(
    '--no-cache', action="store_true", default=False,
    help="Disable the local disk cache")
group.add_argument(
    '--ttl-items', metavar="CACHE_TTL", default="1d",
    help="How long to cache the list of all Warframe items. "
         "Default: %(default)s")
group.add_argument(
    '--ttl-orders', metavar="CACHE_TTL", default="10m",
    help="How long to cache the list of orders for an item. "
         "Default: %(default)s")
group.add_argument(
    '--rate-limit', type=int, default=180,
    help="How fast to send API requests (per minute). Default: %(default)s")

group = parser.add_argument_group('Miscellaneous Options')
group.add_argument(
    '-a', '--all', action="store_true", default=False,
    help="Show all matching users (show more than the top 5 users)")
group.add_argument(
    '-b', '--buyers', action="store_true", default=False,
    help="Show only users looking to buy the item")
group.add_argument(
    '-f', '--file', action="append",
    help="Read list of items from a file, one item per line.")
group.add_argument(
    '-P', '--platform', choices=["pc", "ps4", "switch", "xbox"], default="pc",
    help="The Warframe platform to search. Default: %(default)s.")
group.add_argument(
    '-L', '--language', default="en",
    help="The Warframe language code to search. Default: %(default)s. "
         "E.g. \"de\", \"en\", \"fr\", \"ko\", \"ru\", \"sv\", or \"zh\"")
group.add_argument(
    '-r', '--reverse', action="store_true", default=False,
    help="Reverse the sorting order")

args = parser.parse_args()

if args.debug is not None:
    verbose = args.debug
elif args.verbose <= args.quiet:
    verbose = 0
else:
    # -v = 1, -vv = 3, -vvv = 7, -vvvv = 15 (0xf), ...
    verbose = (1 << (args.verbose - args.quiet)) - 1


request_delay = timedelta(seconds=(60 / args.rate_limit))

cache_dir = args.cache_dir

if verbose & 2:
    print("Cache dir:", args.cache_dir)

if args.clear_cache:
    if verbose & 1:
        print("Clearing cache dir.\n")
    ret = ClearCache()
    quit(0)

if args.file:
    for fil in args.file:
        items = ReadItemsFile(fil)
        args.items.extend(i for i in items if i not in args.items)
elif not args.items:
    parser.error('-f or item arguments are required')

if args.no_cache:
    ttl_items = None
    ttl_orders = None
else:
    ttl_items = StrToTimeDelta(args.ttl_items)
    ttl_orders = StrToTimeDelta(args.ttl_orders)

    if ttl_items is None:
        parser.error("argument --ttl-items: invalid time value: '{}'".format(
                     args.ttl_items))
    if ttl_orders is None:
        parser.error("argument --ttl-orders: invalid time value: '{}'".format(
                     args.ttl_orders))

s = requests.Session()
s.headers.update({"Platform": args.platform, "Language": args.language})
all_items = GetAllItems(s, ttl_items)

if args.summary:
    t = PrettyTable(["Item", "Min", "Avg5", "Max", "StDev5", "Count"],
                    border=False)
    t.align = 'r'
    t.align['Item'] = 'l'
    t.sortby = 'Item'
else:
    t = PrettyTable(["Username", "Price", "Count"], border=False)
    t.align = 'r'
    t.align['Username'] = 'l'

to_lookup = []
for item in args.items:
    matches = FindMatchingItems(item, all_items)
    to_lookup.extend(m for m in matches if m not in to_lookup)
    if len(matches) == 0:
        retval = 1
        if not args.list:
            print("Error: `{}' not found".format(item))
            quit(retval)

if args.list:
    to_lookup.sort(reverse=args.reverse)
    for item in to_lookup:
        print(item)
    quit(retval)

for item in to_lookup:
    orders = GetItemOrders(s, ttl_orders, all_items, item)

    if args.buyers:
        flt = FilterBuyers
        u_type = "Buyers"
    else:
        flt = FilterSellers
        u_type = "Sellers"

    orders = list(filter(flt, orders))
    orders.sort(key=GetPrice, reverse=args.buyers != args.reverse)

    if args.summary:
        AddItemSummary(t, item, orders)
    else:
        if not args.all:
            orders = orders[:5]

        print("--- {} {} ---".format(item, u_type))
        for o in orders:
            name = o['user']['ingame_name']
            t.add_row([name, GetPrice(o), o['quantity']])
        print(t.get_string(), "\n")
        t.clear_rows()

if args.summary:
    print(t.get_string())
    t.clear_rows()

s.close()

quit(0)

# vi: set et ts=4 sw=4 :
