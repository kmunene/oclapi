from django.http import HttpResponse
from rest_framework import mixins, status
from rest_framework.generics import RetrieveAPIView, UpdateAPIView, get_object_or_404, DestroyAPIView, ListAPIView
from rest_framework.response import Response
from oclapi.mixins import ListWithHeadersMixin
from oclapi.models import ResourceVersionModel
from oclapi.permissions import HasAccessToVersionedObject, CanEditConceptDictionaryVersion, CanViewConceptDictionary, CanEditConceptDictionary, CanViewConceptDictionaryVersion
from oclapi.filters import HaystackSearchFilter
from oclapi.views import ResourceVersionMixin, ResourceAttributeChildMixin, ConceptDictionaryUpdateMixin, ConceptDictionaryCreateMixin, SubResourceMixin
from sources.models import Source, SourceVersion
from sources.serializers import SourceCreateSerializer, SourceListSerializer, SourceDetailSerializer, SourceVersionDetailSerializer, SourceVersionListSerializer, SourceVersionCreateSerializer, SourceVersionUpdateSerializer


class SourceBaseView():
    lookup_field = 'source'
    pk_field = 'mnemonic'
    model = Source
    queryset = Source.objects.filter(is_active=True)

    def get_detail_serializer(self, obj, data=None, files=None, partial=False):
        return SourceDetailSerializer(obj, data, files, partial)


class SourceRetrieveUpdateDestroyView(SourceBaseView,
                                      ConceptDictionaryUpdateMixin,
                                      RetrieveAPIView,
                                      DestroyAPIView):
    serializer_class = SourceDetailSerializer

    def initialize(self, request, path_info_segment, **kwargs):
        if 'GET' == request.method:
            self.permission_classes = (CanViewConceptDictionary,)
        else:
            self.permission_classes = (CanEditConceptDictionary,)
        super(SourceRetrieveUpdateDestroyView, self).initialize(request, path_info_segment, **kwargs)


class SourceListView(SourceBaseView,
                     ConceptDictionaryCreateMixin,
                     ListWithHeadersMixin):
    serializer_class = SourceCreateSerializer
    filter_backends = [HaystackSearchFilter]
    solr_fields = {
        'source_type': {'sortable': False, 'filterable': True},
        'name': {'sortable': True, 'filterable': False},
        'last_update': {'sortable': True, 'default': 'desc', 'filterable': False},
        'num_stars': {'sortable': True, 'filterable': False},
        'language': {'sortable': False, 'filterable': True},
    }

    def get(self, request, *args, **kwargs):
        self.serializer_class = SourceDetailSerializer if self.is_verbose(request) else SourceListSerializer
        return self.list(request, *args, **kwargs)


class SourceExtrasView(SourceBaseView, ListAPIView, SubResourceMixin):
    permission_classes = (CanViewConceptDictionary,)

    def initialize(self, request, path_info_segment, **kwargs):
        self.parent_path_info = self.get_parent_in_path(path_info_segment, levels=1)
        self.parent_resource = self.get_object_for_path(self.parent_path_info, self.request)
        if hasattr(self.parent_resource, 'versioned_object'):
            self.parent_resource_version = self.parent_resource
            self.parent_resource = self.parent_resource_version.versioned_object
        else:
            self.parent_resource_version = ResourceVersionModel.get_latest_version_of(self.parent_resource)

    def list(self, request, *args, **kwargs):
        extras = self.parent_resource_version.extras or {}
        return Response(extras)


class SourceVersionBaseView(ResourceVersionMixin):
    lookup_field = 'version'
    pk_field = 'mnemonic'
    model = SourceVersion
    queryset = SourceVersion.objects.filter(is_active=True)
    permission_classes = (HasAccessToVersionedObject,)


class SourceVersionListView(SourceVersionBaseView,
                            mixins.CreateModelMixin,
                            ListWithHeadersMixin):

    def get(self, request, *args, **kwargs):
        self.permission_classes = (CanViewConceptDictionaryVersion,)
        self.serializer_class = SourceVersionDetailSerializer if self.is_verbose(request) else SourceVersionListSerializer
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.serializer_class = SourceVersionCreateSerializer
        self.permission_classes = (CanEditConceptDictionaryVersion,)
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not self.versioned_object:
            return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)
        if serializer.is_valid():
            self.pre_save(serializer.object)
            self.object = serializer.save(force_insert=True, versioned_object=self.versioned_object)
            if serializer.is_valid():
                self.post_save(self.object, created=True)
                headers = self.get_success_headers(serializer.data)
                serializer = SourceVersionDetailSerializer(self.object)
                return Response(serializer.data, status=status.HTTP_201_CREATED,
                                headers=headers)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SourceVersionRetrieveUpdateView(SourceVersionBaseView, RetrieveAPIView, UpdateAPIView):
    is_latest = False

    def initialize(self, request, path_info_segment, **kwargs):
        if 'GET' == request.method:
            self.permission_classes = (CanViewConceptDictionaryVersion,)
            self.serializer_class = SourceVersionDetailSerializer
        else:
            self.permission_classes = (CanEditConceptDictionaryVersion,)
            self.serializer_class = SourceVersionUpdateSerializer
        self.is_latest = kwargs.pop('is_latest', False)
        super(SourceVersionRetrieveUpdateView, self).initialize(request, path_info_segment, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.versioned_object:
            return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)

        self.object = self.get_object()
        created = False
        save_kwargs = {'force_update': True, 'versioned_object': self.versioned_object}
        success_status_code = status.HTTP_200_OK

        serializer = self.get_serializer(self.object, data=request.DATA,
                                         files=request.FILES, partial=True)

        if serializer.is_valid():
            self.pre_save(serializer.object)
            self.object = serializer.save(**save_kwargs)
            if serializer.is_valid():
                self.post_save(self.object, created=created)
                serializer = SourceVersionDetailSerializer(self.object)
                return Response(serializer.data, status=success_status_code)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_object(self, queryset=None):
        if self.is_latest:
            # Determine the base queryset to use.
            if queryset is None:
                queryset = self.filter_queryset(self.get_queryset())
            else:
                pass  # Deprecation warning

            filter_kwargs = {'released': True}
            obj = get_object_or_404(queryset, **filter_kwargs)

            # May raise a permission denied
            self.check_object_permissions(self.request, obj)
            return obj
        return super(SourceVersionRetrieveUpdateView, self).get_object(queryset)


class SourceVersionRetrieveUpdateDestroyView(SourceVersionRetrieveUpdateView, DestroyAPIView):

    def destroy(self, request, *args, **kwargs):
        version = self.get_object()
        if version.released:
            errors = {'non_field_errors' : ['Cannot deactivate a version that is currently released.  Please release another version before deactivating this one.']}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        return super(SourceVersionRetrieveUpdateDestroyView, self).destroy(request, *args, **kwargs)


class SourceVersionChildListView(ResourceAttributeChildMixin, ListWithHeadersMixin):
    lookup_field = 'version'
    pk_field = 'mnemonic'
    model = SourceVersion
    permission_classes = (HasAccessToVersionedObject,)

    def get(self, request, *args, **kwargs):
        self.serializer_class = SourceVersionDetailSerializer if self.is_verbose(request) else SourceVersionListSerializer
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super(SourceVersionChildListView, self).get_queryset()
        return queryset.filter(parent_version=self.resource_version, is_active=True)
