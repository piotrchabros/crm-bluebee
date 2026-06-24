"""Authenticated download for uploaded attachments.

Replaces the public ``/media/`` link: the file is streamed only to an
authenticated user in the attachment's owning org. Cross-org (or unknown) ids
return 404 so the endpoint never confirms a file exists in another org.
"""

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.models import Attachments
from common.permissions import HasOrgContext


class AttachmentDownloadView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request, pk):
        try:
            att = Attachments.objects.get(pk=pk, org=request.profile.org)
        except (Attachments.DoesNotExist, ValidationError, ValueError):
            raise Http404
        if not att.attachment:
            raise Http404
        try:
            fh = att.attachment.open("rb")
        except (FileNotFoundError, OSError):
            raise Http404
        # Inline so PDFs/images open in the browser; the filename is preserved
        # for the "Save as" dialog and for types the browser downloads.
        return FileResponse(fh, as_attachment=False, filename=att.file_name)
