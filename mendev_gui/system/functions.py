import random
from operator import itemgetter
from pathlib import Path
from decimal import Decimal, InvalidOperation


def to_decimal(txt):
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


# Order_by function
def order_by_add(order_by_list, order):
    # Remove value from list and switch sequence
    current_order = None
    desc_order = '-' + order
    for value in order_by_list:
        if value == order or value == desc_order:
            current_order = value
    if current_order:
        order_by_list.remove(current_order)
        if not current_order.startswith('-'):
            order = desc_order

    # Add as first in list
    order_by_list.insert(0, order)

    return order_by_list


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def list_to_sql_string(value_list):
    in_string = "'"
    first = True
    for value in value_list:
        if not first:
            in_string += "','"
        first = False
        in_string += str(value)
    in_string += "'"
    return in_string


def local_path(path='/'):
    path = Path(path)

    if not path.is_absolute():
        if len(path.parts) and path.parts[0] != '/':
            path = Path('/') / path
        path = path.resolve()

    return path


def multisort(xs, order_by_list):
    for order_by in reversed(order_by_list):
        if order_by[0:1] == '-':
            key = order_by[1:]
            reverse = True
        else:
            key = order_by
            reverse = False
        xs.sort(key=itemgetter(key), reverse=reverse)
    return xs


def random_string(length):
    random_string = ''
    for _ in range(length):
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        random_integer = random_integer - 32 if flip_bit == 1 else random_integer
        random_string += (chr(random_integer))

    return random_string
