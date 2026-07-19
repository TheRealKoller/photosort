from photosort.opencloud.webdav_xml import parse_multistatus

MULTISTATUS_RESPONSE = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/dav/spaces/storage-users-1$userid/FolderName/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
        <d:getetag>&quot;e83367534cc595a45d706857fa5f03d8&quot;</d:getetag>
        <d:getlastmodified>Mon, 28 Aug 2023 20:45:10 GMT</d:getlastmodified>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-users-1$userid/FolderName/Sub%20Folder/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
        <d:getetag>&quot;subfolder-etag&quot;</d:getetag>
        <d:getlastmodified>Mon, 28 Aug 2023 20:45:11 GMT</d:getlastmodified>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-users-1$userid/FolderName/document.txt</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype></d:resourcetype>
        <d:getetag>&quot;75115347c74701a3be9c635ddebbf5c4&quot;</d:getetag>
        <d:getlastmodified>Mon, 28 Aug 2023 20:45:03 GMT</d:getlastmodified>
        <d:getcontentlength>5</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-users-1$userid/FolderName/broken.jpg</d:href>
    <d:propstat>
      <d:prop>
        <d:getcontentlength/>
      </d:prop>
      <d:status>HTTP/1.1 404 Not Found</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


def test_parses_folder_and_file_entries() -> None:
    entries = parse_multistatus(MULTISTATUS_RESPONSE.encode())

    by_name = {entry.name: entry for entry in entries}

    assert by_name["FolderName"].is_collection is True
    assert by_name["FolderName"].etag == '"e83367534cc595a45d706857fa5f03d8"'
    assert by_name["FolderName"].content_length is None

    assert by_name["document.txt"].is_collection is False
    assert by_name["document.txt"].content_length == 5
    assert by_name["document.txt"].etag == '"75115347c74701a3be9c635ddebbf5c4"'


def test_decodes_url_encoded_names() -> None:
    entries = parse_multistatus(MULTISTATUS_RESPONSE.encode())

    names = {entry.name for entry in entries}
    assert "Sub Folder" in names


def test_skips_propstat_blocks_with_non_200_status() -> None:
    entries = parse_multistatus(MULTISTATUS_RESPONSE.encode())

    assert "broken.jpg" not in {entry.name for entry in entries}


def test_parses_last_modified_as_datetime() -> None:
    entries = parse_multistatus(MULTISTATUS_RESPONSE.encode())

    document = next(e for e in entries if e.name == "document.txt")
    assert document.last_modified is not None
    assert document.last_modified.year == 2023
    assert document.last_modified.month == 8
    assert document.last_modified.day == 28
