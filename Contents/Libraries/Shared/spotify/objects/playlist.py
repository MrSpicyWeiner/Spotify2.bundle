from spotify.core.revent import REvent
from spotify.core.uri import Uri
from spotify.objects.base import Descriptor, PropertyProxy
from spotify.proto import playlist4changes_pb2
from spotify.proto import playlist4content_pb2


class PlaylistItem(Descriptor):
    __protobuf__ = playlist4content_pb2.Item

    uri = PropertyProxy(func=Uri.from_uri)
    name = PropertyProxy

    added_by = PropertyProxy('attributes.added_by')

    def fetch(self, start=0, count=100, callback=None):
        if callback:
            return self.sp.playlist(self.uri, start,count, callback)

        # Fetch full playlist detail
        event = REvent()
        self.sp.playlist(self.uri, start, count, callback=lambda pl: event.set(pl))

        # Wait until result is available
        return event.wait()


class Playlist(Descriptor):
    __protobuf__ = playlist4changes_pb2.ListDump
    __node__ = 'playlist'

    uri = PropertyProxy(func=Uri.from_uri)
    name = PropertyProxy('attributes.name')
    image = PropertyProxy

    length = PropertyProxy
    position = PropertyProxy('contents.pos')

    items = PropertyProxy('contents.items', 'PlaylistItem')
    truncated = PropertyProxy('contents.truncated')

    def list(self, group=None, flat=False):
        if group:
            # Pull the code from a group URI
            parts = group.split(':')
            group = parts[2] if len(parts) == 4 else group

        path = []

        for item in self.items:
            if item.uri.type == 'start-group':
                # Ignore groups if we are returning a flat list
                if flat:
                    continue

                # Only return placeholders on the root level
                if (not group and not path) or (path and path[-1] == group):
                    # Return group placeholder
                    yield PlaylistItem(self.sp).dict_update({
                        'uri': Uri.from_uri('spotify:group:%s:%s' % (item.uri.code, item.uri.title)),
                        'name': item.uri.title
                    })

                path.append(item.uri.code)
                continue
            elif item.uri.type == 'end-group':
                # Group close tag
                if path and path.pop() == group:
                    return

                continue

            if group is None:
                # Ignore if we are inside a group
                if path and not flat:
                    continue
            else:
                # Ignore if we aren't inside the specified group
                if not path or path[-1] != group:
                    continue

            # Return item
            yield item

    def fetch(self, group=None, flat=False):
        if self.uri.type == 'rootlist':
            return self.fetch_playlists(group, flat)

        if self.uri.type in ['playlist', 'starred']:
            return self.fetch_tracks()

        return None

    def fetch_playlists(self, group=None, flat=False):
        for item in self.list(group, flat):
            # Return plain PlaylistItem for groups
            if item.uri.type == 'group':
                yield item
                continue

            yield item.fetch()

    def fetch_tracks(self):
        uris = [item.uri for item in self.items]

        event = REvent()
        self.sp.metadata(uris, callback=lambda items: event.set(items))

        return event.wait()

    @classmethod
    def from_dict(cls, sp, data, types):
        uri = Uri.from_uri(data.get('uri'))

        return cls(sp, {
            'uri': uri,
            'attributes': {
                'name': data.get('name')
            },
            'image': data.get('image')
        }, types)