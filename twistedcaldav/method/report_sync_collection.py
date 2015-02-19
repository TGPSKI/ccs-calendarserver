##
# Copyright (c) 2010-2015 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##

"""
DAV sync-collection report
"""

__all__ = ["report_DAV__sync_collection"]

from twext.python.log import Logger

from twisted.internet.defer import inlineCallbacks, returnValue

from twistedcaldav.config import config
from twistedcaldav.method.report_common import (
    _namedPropertiesForResource, responseForHref
)

from txdav.common.icommondatastore import ConcurrentModification
from txdav.xml import element

from txweb2 import responsecode
from txweb2.dav.http import ErrorResponse
from txweb2.dav.http import MultiStatusResponse
from txweb2.dav.util import joinURL
from txweb2.http import HTTPError, StatusResponse

import functools

log = Logger()

@inlineCallbacks
def report_DAV__sync_collection(self, request, sync_collection):
    """
    Generate a sync-collection REPORT.
    """

    # These resource support the report
    if not config.EnableSyncReport or element.Report(element.SyncCollection(),) not in self.supportedReports():
        log.error("sync-collection report is only allowed on calendar/inbox/addressbook/notification collection resources %s" % (self,))
        raise HTTPError(ErrorResponse(
            responsecode.FORBIDDEN,
            element.SupportedReport(),
            "Report not supported on this resource",
        ))

    responses = []

    # Do not support limit
    if sync_collection.sync_limit is not None:
        raise HTTPError(ErrorResponse(
            responsecode.INSUFFICIENT_STORAGE_SPACE,
            element.NumberOfMatchesWithinLimits(),
            "Report limit not supported",
        ))

    # Process Depth and sync-level for backwards compatibility
    # Use sync-level if present and ignore Depth, else use Depth
    if sync_collection.sync_level:
        depth = sync_collection.sync_level
        if depth == "infinite":
            depth = "infinity"
        descriptor = "DAV:sync-level"
    else:
        depth = request.headers.getHeader("depth", None)
        descriptor = "Depth header without DAV:sync-level"

    if depth not in ("1", "infinity"):
        log.error("sync-collection report with invalid depth header: %s" % (depth,))
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, "Invalid %s value" % (descriptor,)))

    propertyreq = sync_collection.property.children if sync_collection.property else None

    # Do some optimization of access control calculation by determining any inherited ACLs outside of
    # the child resource loop and supply those to the checkPrivileges on each child.
    filteredaces = (yield self.inheritedACEsforChildren(request))

    changed, removed, notallowed, newtoken, resourceChanged = yield self.whatchanged(sync_collection.sync_token, depth)

    # Now determine which valid resources are readable and which are not
    ok_resources = []
    forbidden_resources = []
    if changed:
        yield self.findChildrenFaster(
            depth,
            request,
            lambda x, y: ok_resources.append((x, y)),
            lambda x, y: forbidden_resources.append((x, y)),
            None,
            None,
            changed,
            (element.Read(),),
            inherited_aces=filteredaces
        )

    if resourceChanged:
        ok_resources.append((self, request.uri))

    for child, child_uri in ok_resources:
        href = element.HRef.fromString(child_uri)
        try:
            yield responseForHref(
                request,
                responses,
                href,
                child,
                functools.partial(_namedPropertiesForResource, dataAllowed=False, forbidden=False) if propertyreq else None,
                propertyreq)
        except ConcurrentModification:
            # This can happen because of a race-condition between the
            # time we determine which resources exist and the deletion
            # of one of these resources in another request.  In this
            # case, we ignore the now missing resource rather
            # than raise an error for the entire report.
            log.error("Missing resource during sync: %s" % (href,))

    for child, child_uri in forbidden_resources:
        href = element.HRef.fromString(child_uri)
        try:
            yield responseForHref(
                request,
                responses,
                href,
                child,
                functools.partial(_namedPropertiesForResource, dataAllowed=False, forbidden=True) if propertyreq else None,
                propertyreq)
        except ConcurrentModification:
            # This can happen because of a race-condition between the
            # time we determine which resources exist and the deletion
            # of one of these resources in another request.  In this
            # case, we ignore the now missing resource rather
            # than raise an error for the entire report.
            log.error("Missing resource during sync: %s" % (href,))

    for name in removed:
        href = element.HRef.fromString(joinURL(request.uri, name))
        responses.append(element.StatusResponse(element.HRef.fromString(href), element.Status.fromResponseCode(responsecode.NOT_FOUND)))

    for name in notallowed:
        href = element.HRef.fromString(joinURL(request.uri, name))
        responses.append(element.StatusResponse(element.HRef.fromString(href), element.Status.fromResponseCode(responsecode.NOT_ALLOWED)))

    if not hasattr(request, "extendedLogItems"):
        request.extendedLogItems = {}
    request.extendedLogItems["responses"] = len(responses)

    responses.append(element.SyncToken.fromString(newtoken))

    returnValue(MultiStatusResponse(responses))
