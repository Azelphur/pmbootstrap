"""
Copyright 2018 Oliver Smith

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
In order to stay as compatible to Alpine's apk as possible, this code
is heavily based on:

https://git.alpinelinux.org/cgit/apk-tools/tree/src/version.c
"""


def token_value(string):
    """
    Return the associated value for a given token string (we parse
    through the version string one token at a time).

    :param string: a token string
    :returns: integer associated to the token (so we can compare them in
              functions further below, a digit (1) looses against a
              letter (2), because "letter" has a higher value).

    C equivalent: enum PARTS
    """
    order = {
        "invalid": -1,
        "digit_or_zero": 0,
        "digit": 1,
        "letter": 2,
        "suffix": 3,
        "suffix_no": 4,
        "revision_no": 5,
        "end": 6
    }
    return order[string]


def next_token(previous, rest):
    """
    Parse the next token in the rest of the version string, we're
    currently looking at.

    We do *not* get the value of the token, or advance the rest string
    beyond the whole token, that is what the get_token() function does
    (see below).

    :param previous: the token before
    :param rest: of the version string
    :returns: (next, rest) next is the upcoming token, rest is the
              input "rest" string with one leading '.', '_' or '-'
              character removed (if there was any).

    C equivalent: next_token()
    """
    next = "invalid"
    char = rest[:1]

    # Tokes, which do not change rest
    if not len(rest):
        next = "end"
    elif previous in ["digit", "digit_or_zero"] and char.islower():
        next = "letter"
    elif previous == "letter" and char.isdigit():
        next = "digit"
    elif previous == "suffix" and char.isdigit():
        next = "suffix_no"

    # Tokens, which remove the first character of rest
    else:
        if char == ".":
            next = "digit_or_zero"
        elif char == "_":
            next = "suffix"
        elif rest.startswith("-r"):
            next = "revision_no"
            rest = rest[1:]
        elif char == "-":
            next = "invalid"
        rest = rest[1:]

    # Validate current token
    # Check if the transition from previous to current is valid
    if token_value(next) < token_value(previous):
        if not ((next == "digit_or_zero" and previous == "digit") or
                (next == "suffix" and previous == "suffix_no") or
                (next == "digit" and previous == "letter")):
            next = "invalid"
    return (next, rest)


def parse_suffix(rest):
    """
    Cut off the suffix of rest (which is now at the beginning of the
    rest variable, but regarding the whole version string, it is a
    suffix), and return a value integer (so it can be compared later,
    "beta" > "alpha" etc).

    :param rest: what is left of the version string, that we are
                 currently parsing, starts with a "suffix" value
                 (see below for valid suffixes).
    :returns: (rest, value) rest is the input "rest" string without the
              suffix, value is a signed integer (negative for pre-,
              positive for post-suffixes).

    C equivalent: get_token(), case TOKEN_SUFFIX
    """
    suffixes = {
        "pre": ["alpha", "beta", "pre", "rc"],
        "post": ["cvs", "svn", "git", "hg", "p"]
    }

    for name, suffixes in suffixes.items():
        for i, suffix in enumerate(suffixes):
            if not rest.startswith(suffix):
                continue
            rest = rest[len(suffix):]
            value = i
            if name == "pre":
                value = value - len(suffixes)
            return (rest, value)
    return (rest, 0)


def get_token(previous, rest):
    """
    This function does three things:
    * get the next token
    * get the token value
    * cut-off the whole token from rest

    :param previous: the token before
    :param rest: of the version string
    :returns: (next, value, rest) next is the new token string,
              value is an integer for comparing, rest is the rest of the
              input string.

    C equivalent: get_token()
    """
    # Set defaults
    value = 0
    next = "invalid"

    # Bail out if at the end
    if not len(rest):
        return ("end", 0, rest)

    # Cut off leading zero digits
    if previous == "digit_or_zero" and rest.startswith("0"):
        while rest.startswith("0"):
            rest = rest[1:]
            value -= 1
        next = "digit"

    # Add up numeric values
    elif previous in ["digit_or_zero", "digit", "suffix_no",
                      "revision_no"]:
        for i in range(len(rest)):
            while len(rest) and rest[0].isdigit():
                value *= 10
                value += int(rest[i])
                rest = rest[1:]

    # Append chars or parse suffix
    elif previous == "letter":
        value = rest[0]
        rest = rest[1:]
    elif previous == "suffix":
        (rest, value) = parse_suffix(rest)

    # Invalid previous token
    else:
        value = -1

    # Get the next token (for non-leading zeros)
    if(not len(rest)):
        next = "end"
    elif(next == "invalid"):
        (next, rest) = next_token(previous, rest)

    return (next, value, rest)


def validate(version):
    """
    Check whether one version string is valid.

    :param version: full version string
    :returns: True when the version string is valid

    C equivalent: apk_version_validate()
    """
    current = "digit"
    rest = version
    while current != "end":
        (current, value, rest) = get_token(current, rest)
        if current == "invalid":
            return False
    return True


def compare(a_version, b_version, fuzzy=False):
    """
    Compare two versions A and B to find out which one is higher, or if
    both are equal.

    :param a_version: full version string A
    :param b_version: full version string B
    :param fuzzy: treat version strings, which end in different token
                  types as equal

    :returns:
        (a <  b): -1
        (a == b):  0
        (a >  b):  1

    C equivalent: apk_version_compare_blob_fuzzy()
    """

    # Defaults
    a_token = "digit"
    b_token = "digit"
    a_value = 0
    b_value = 0
    a_rest = a_version
    b_rest = b_version

    # Parse A and B one token at a time, until one string ends, or the
    # current token has a different type/value
    while (a_token == b_token and a_token not in ["end", "invalid"] and
           a_value == b_value):
        (a_token, a_value, a_rest) = get_token(a_token, a_rest)
        (b_token, b_value, b_rest) = get_token(b_token, b_rest)

    # Compare the values inside the last tokens
    if a_value < b_value:
        return -1
    if a_value > b_value:
        return 1

    # Equal: When tokens are the same strings, or when the value
    # is the same and fuzzy compare is enabled
    if a_token == b_token or fuzzy:
        return 0

    # Leading version components and their values are equal, now the
    # non-terminating version is greater unless it's a suffix
    # indicating pre-release
    if a_token == "suffix":
        (a_token, a_value, a_rest) = get_token(a_token, a_rest)
        if a_value < 0:
            return -1
    if b_token == "suffix":
        (b_token, b_value, b_rest) = get_token(b_token, b_rest)
        if b_value < 0:
            return 1

    # Compare the token value (e.g. digit < letter)
    if token_value(a_token) > token_value(b_token):
        return -1
    if token_value(a_token) < token_value(b_token):
        return 1

    # The tokens are not the same, but previous checks revealed that it
    # is equal anyway (e.g. "1.0" == "1").
    return 0
