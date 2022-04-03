from piccolo import columns
from piccolo.apps.user.tables import BaseUser
from piccolo.table import Table


class Author(Table):
    id = columns.UUID(primary_key=True)
    user = columns.ForeignKey(BaseUser)


class Post(Table):
    id = columns.UUID(primary_key=True)
    title = columns.Varchar(length=100)
    body = columns.Text()
    author = columns.ForeignKey(Author)
