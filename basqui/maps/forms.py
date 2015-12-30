import re
from maps.models import *
from maps.mapnik_parameters import *
from layers.models import *
from django import forms
from django.utils.safestring import mark_safe
from django.forms.formsets import DELETION_FIELD_NAME
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML, Submit, Button, Reset, Field
from crispy_forms.bootstrap import AccordionGroup, Accordion, TabHolder, Tab, PrependedAppendedText


messages_layout = Layout(
    HTML('''{% if messages %}
            <p>
                {% for message in messages %}
                    {% if message.level == DEFAULT_MESSAGE_LEVELS.ERROR %}
                        <p class='has-error'><strong><em>Error: {{ message }}</em></strong></p>
                    {% else %}
                        <p><strong><em>{{ message }}</em></strong></p>
                    {% endif %}
                {% endfor %}
            </p>
            {% endif %}''')
)


FORMAT = [("shp", "Shapefile"),
            ("tab", "MapInfo TAB"),
            ("json", "GeoJSON"),
            ("kml", "KML/KMZ"),
            ("sqlite", "SQLite/Spatialite")]

CHARACTER_ENCODINGS = [("ascii", "ASCII"),
                    ("latin1", "Latin-1"),
                    ("utf8", "UTF-8")]


GEOM_TYPE = [("Point", "Point/MultiPoint"),
            ("LineString", "LineString/MultiLineString"),
            ("Polygon", "Polygon/MultiPolygon")]


class CreateMapForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(CreateMapForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'createMapForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.attrs = {"style":"width:600px;"}
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Create map form',
                    'name', 'layers', 'wms',
                css_class='in')
            ),
            Div(
                HTML("<pre>"),
                HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="createMap({{ folder.pk }})" />'),
                Reset('cancel', 'Reset'),
                messages_layout,
                HTML("</pre>")
            )
        )

    class Meta:
        model = BasquiMap
        fields = ('name', 'layers', 'wms')


class CreateVectorLayerForm(forms.ModelForm):
    geom_type = forms.ChoiceField(choices=GEOM_TYPE, initial="Point/MultiPoint", label='Geometry type')
    def __init__(self, *args, **kwargs):
        super(CreateVectorLayerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-6'
        self.helper.attrs = {"style":"width:400px;"}
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Create vector layer form',
                    'name', 'geom_type',
                css_class='in')
            ),
            Div(
                HTML("<pre>"),
                HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="createLayer({{ folder.pk }})" />'),
                Reset('cancel', 'Reset'),
                messages_layout,
                HTML("</pre>")
            )
        )

    class Meta:
        model = Shapefile
        fields  = ('name', 'geom_type')


class ImportVectorForm(forms.Form):
    character_encoding = forms.ChoiceField(choices=CHARACTER_ENCODINGS, initial="utf8")
    format = forms.ChoiceField(choices=FORMAT, initial="shapefile")
    file = forms.FileField(help_text="Select a zipped file")

    def __init__(self, *args, **kwargs):
        super(ImportVectorForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'importVectorForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.attrs = {"style":"width:600px;"}
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Import vector file form',
                    'character_encoding', 'format', 'file',
                )
            ),
            Div(
                HTML("<pre>"),
                HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="importLayer({{ folder.pk }})" />'),
                Reset('cancel', 'Reset'),
                messages_layout,
                HTML("</pre>")
            )
        )


class ImportOSMForm(forms.Form):
    name = forms.CharField(label='Layer name')
    query = forms.CharField(label='Overpass API query',
            widget=forms.Textarea(),
            initial='''node["amenity"="school"](45.3490,-74.1328,47.647,-72.0234);out body;''',
            help_text='<a href="http://wiki.openstreetmap.org/wiki/Overpass_API/Language_Guide" target="blank">Overpass Api Documentation</a>')
    maxX = forms.FloatField()
    maxY = forms.FloatField()
    minX = forms.FloatField()
    minY = forms.FloatField()
    def __init__(self, *args, **kwargs):
        super(ImportOSMForm, self).__init__(*args, **kwargs)
        self.fields['maxX'].label = False
        self.fields['maxY'].label = False
        self.fields['minX'].label = False
        self.fields['minY'].label = False
        self.helper = FormHelper()
        self.helper.form_id = "importOSMForm"
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Bounding box',
                    Div(
                        Div(
                            Div(PrependedAppendedText('maxY', 'Max Y'), css_class='col-lg-6 col-lg-offset-3'),
                        css_class='row'),
                        Div(
                            Div(PrependedAppendedText('minX', 'Min X'), css_class='col-lg-6'),
                            Div(PrependedAppendedText('maxX', 'Max X'), css_class='col-lg-6'),
                        css_class='row'),
                        Div(
                            Div(PrependedAppendedText('minY', 'Min Y'), css_class='col-lg-6 col-lg-offset-3'),
                        css_class='row'),
                    css_class='container-fluid', css_id='bbox-div'),
                css_class='in')
            ),
            Accordion(
                AccordionGroup('Import OSM data form',
                    'name','query',
                css_class='in')
            ),
            Div(
                HTML("<pre>"),
                HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="importOSM({{ folder.pk }})" />'),
                Reset('cancel', 'Reset'),
                messages_layout,
                HTML("</pre>")
            )
        )


class ExportVectorForm(forms.Form):
    character_encoding = forms.ChoiceField(choices=CHARACTER_ENCODINGS, initial="utf8")
    EPSG = forms.IntegerField()
    format = forms.ChoiceField(choices=FORMAT, initial="shapefile")
    layers = forms.ModelMultipleChoiceField(queryset=Shapefile.objects.all())
    merge = forms.BooleanField(required=False, help_text="Merge selected layers into one file")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.parent = kwargs.pop("parent")
        super(ExportVectorForm, self).__init__(*args, **kwargs)
        self.fields['layers'].queryset = Shapefile.objects.filter(parent= self.parent, created_by__username=self.user)
        self.helper = FormHelper()
        self.helper.form_id = 'exportForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.attrs = {"style":"width:600px;"}
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Import vector file form',
                    'character_encoding', 'EPSG', 'format', 'layers', 'merge',
                css_class='in')
            ),
            Div(
                HTML("<pre>"),
                HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="exportLayer({{ folder.pk }})" />'),
                Reset('cancel', 'Reset'),
                messages_layout,
                HTML("</pre>")
            )
        )

class WMSLayerForm(forms.ModelForm):
    class Meta:
        model = WMSLayer
        exclude = ('wms', 'layer_name', 'position')


class NewWMSForm(forms.ModelForm):
    class Meta:
        model = WMS
        exclude = ('created_by',)


class EditWMSForm(forms.ModelForm):
    class Meta:
        model = WMS
        exclude = ('created_by', 'srs', 'url')


class HoverFeatureAttributeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.feat_data = kwargs.pop("feat_data")
        self.feat_id_relat = kwargs.pop("feat_id_relat")
        super(HoverFeatureAttributeForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        self.helper = FormHelper()
        self.helper.form_id = 'featureAttributesForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.attrs = {"style":"width:370px;"}
        self.helper.disable_csrf = True
        self.helper.label_class = 'col-sm-4'
        self.helper.field_class = 'col-sm-8'
        self.fields['id'] = forms.CharField(initial=self.feat_id_relat, label='ID :', widget=forms.TextInput(attrs={'readonly': False}))
        for key,value in self.feat_data.iteritems():
            self.fields[str(key)] = forms.CharField(initial=value, label=key + " :")


class AttributeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AttributeForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['type'].widget.attrs['disabled'] = True
            self.fields['type'].required = False
            self.fields['width'].widget.attrs['readonly'] = True
            self.fields['precision'].widget.attrs['readonly'] = True

    def clean_type(self):
        if self.instance and self.instance.pk:
            return self.instance.type
        else:
            return self.cleaned_data['type']

    FIELD_TYPE = [('', '--Choose a type--'),
                        (0, 'Integer'),
                        (2, 'Float'),
                        (4, 'String'),
                        (9, 'Date'),
                        (10, 'Time')]

    type = forms.ChoiceField(choices=FIELD_TYPE)

    class Meta:
        model = Attribute
        exclude = ('shapefile',)


class AttributesFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super(AttributesFormSetHelper, self).__init__(*args, **kwargs)
        self.template = '../templates/crispyforms/attributes_inline_formset.html'
        self.form_id = 'editFieldForm'
        self.attrs = {"style":"width:800px;"}
        self.layout = Layout(
            'name','type','width', 'precision'
        )


class LayerLinkWidget(forms.Widget):
    def __init__(self, obj, attrs=None):
        self.object = obj
        super(LayerLinkWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if self.object.pk:
            return mark_safe(
                u'''<a href="javascript:void(0)" onClick="alert('clicked %s')">%s</a>''' %\
                      (
                       self.object.name, self.object.name
                       )
            )
        else:
            return mark_safe(u'')


class LayerStyleLinkWidget(forms.Widget):
    def __init__(self, obj, attrs=None):
        self.object = obj
        super(LayerStyleLinkWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if self.object.pk:
            return mark_safe(
                u'''<a class="btn btn-default btn-xs" href="javascript:void(0)" onClick="layerStyleWin('%s', '%s')"><span class="glyphicon glyphicon-pencil" style="color:blue" aria-hidden="true"></span></a>''' %\
                      (
                       self.object.pk, self.object.layer.name
                       )
            )
        else:
            return mark_safe(u'')


class LayerLabelLinkWidget(forms.Widget):
    def __init__(self, obj, attrs=None):
        self.object = obj
        super(LayerLabelLinkWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if self.object.pk:
            return mark_safe(
                u'''<a class="btn btn-default btn-xs" href="javascript:void(0)" onClick="layerLabelWin('%s', '%s')"><span class="glyphicon glyphicon-font" aria-hidden="true"></span></a>''' %\
                      (
                       self.object.pk, self.object.layer.name
                       )
            )
        else:
            return mark_safe(u'')


class LayerMapOptionsForm(forms.ModelForm):
    layerLink = forms.CharField(label='<span class="glyphicon glyphicon-file" aria-hidden="true"></span> Layer(s)', required=False)
    styleLink = forms.CharField(label='Style', required=False)
    labelLink = forms.CharField(label='Label', required=False)
    remove = forms.BooleanField(label='<span class="glyphicon glyphicon-remove" aria-hidden="true"></span>', required=False)

    def __init__(self, *args, **kwargs):
        super(LayerMapOptionsForm, self).__init__(*args, **kwargs)
        self.fields['layerLink'].widget = LayerLinkWidget(self.instance.layer)
        self.fields['styleLink'].widget = LayerStyleLinkWidget(self.instance)
        self.fields['labelLink'].widget = LayerLabelLinkWidget(self.instance)
        self.fields['style_visible'].label = '<span class="glyphicon glyphicon-eye-open" aria-hidden="true"></span>'
        self.fields['label_visible'].label = '<span class="glyphicon glyphicon-tags" aria-hidden="true"></span>'

    def save(self, commit=True, force_insert=False, force_update=False, *args, **kwargs):
        remove = self.cleaned_data['remove']
        print remove
        instance = super(LayerMapOptionsForm, self).save(commit=False,  *args, **kwargs)
        if remove == True:
            instance.delete()
        else:
            instance.save()
        return instance


    class Meta:
        model = LayerMapOptions
        fields =  ['layerLink', 'styleLink', 'style_visible', 'labelLink', 'label_visible', 'remove']
        widgets= {
            'id' : forms.HiddenInput(attrs={'class': 'layer_id'}),
        }




class LayerMapOptionsFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super(LayerMapOptionsFormSetHelper, self).__init__(*args, **kwargs)
        self.template = '../templates/crispyforms/layerMapOptions_inline_formset.html'
        self.form_tag = False
        self.layout = Layout(
            'layerLink', Submit('Style', 'style'), 'style_visible', 'labelLink', 'label_visible', 'remove', 'id',
        )


class MapOptionsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MapOptionsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-6'
        self.helper.field_class = 'col-lg-6'
        self.helper.layout = Layout(
            Div(
                'map_width', 'map_height', 'center_lat', 'center_long', 'zoom_level',
                Div(
                    HTML("<pre>"),
                    HTML('<input type="button" value="Submit" class="btn btn-primary" onclick="saveMapOptions({{ map.pk }})" />'),
                    Reset('cancel', 'Reset'),
                    messages_layout,
                    HTML("</pre>"),
                    css_class="modal-footer"
                ),
                css_class="modal-body"
            )
        )

    class Meta:
        model = BasquiMap
        fields = ['map_width', 'map_height', 'center_lat', 'center_long', 'zoom_level']



class PointLayerStyleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PointLayerStyleForm, self).__init__(*args, **kwargs)
        markers = Marker.objects.all()
##        choices = [(marker.id, '%s' % marker.name)]
##        choices.insert(0,('0','Please Choose'))
        self.fields['marker'] = forms.ModelChoiceField(queryset=markers, empty_label="-- Select a symbol --")
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.label_class = 'col-lg-5'
        self.helper.field_class = 'col-lg-7'
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Style options',
                    Field('marker', css_class="markerSelect"), Field('fill', css_class='spectrum'),'fill_opacity',
                    Field('stroke_color', css_class='spectrum'), 'stroke_width', 'stroke_opacity', 'transform',
                    active=True
                ),
                 AccordionGroup('Placement options',
                    'allow_overlap', 'spacing', 'max_error',
                    active=False
                 ),
                 AccordionGroup('Filter & constraints',
                   'minScale', 'maxScale',  'filter',
                    active=False
                )
            ),
            Div('id', 'DELETE', css_class="hiddenDiv", style="display:none")
        )

    class Meta:
        model = LayerStyle
        fields = ['marker', 'fill', 'fill_opacity', 'stroke_color', 'stroke_width', 'stroke_opacity', 'transform',
                    'allow_overlap', 'spacing', 'max_error',
                    'minScale', 'maxScale',  'filter']


class PolylineLayerStyleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PolylineLayerStyleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.label_class = 'col-lg-5'
        self.helper.field_class = 'col-lg-7'
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Style options',
                    Field('stroke_color', css_class='spectrum'), 'stroke_width', 'stroke_opacity', 'stroke_linejoin', 'stroke_linecap', 'stroke_offset', 'dash_array',
                    active=True
                ),
                AccordionGroup('Advandced options',
                    'stroke_rasterizer', 'gamma', 'gamma_method', 'smooth', 'simplify_tolerance',
                    active=False
                ),
                AccordionGroup('Filter & constraints',
                   'minScale', 'maxScale',  'filter',
                    active=False
                )
            ),
            Div('id', 'DELETE', css_class="hiddenDiv", style="display:none")
        )

    class Meta:
        model = LayerStyle
        fields = ['filter', 'minScale', 'maxScale',
                    'stroke_color', 'stroke_width', 'stroke_opacity', 'stroke_linejoin', 'stroke_linecap', 'stroke_offset', 'dash_array',
                    'stroke_rasterizer', 'gamma', 'gamma_method', 'smooth', 'simplify_tolerance'
                    ]


    def clean_dash_array(self):
        data = self.cleaned_data['dash_array']
        if data:
            try:
                data_cleaned = [tuple(float(i) for i in el.strip('()').split(',')) for el in data.split('),(')]
            except:
                raise forms.ValidationError("Except: You must enter tuple(s) of int or float delimited with coma - Ex: (1,1),(2,2)")
        return data


class PolygonLayerStyleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PolygonLayerStyleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.label_class = 'col-lg-5'
        self.helper.field_class = 'col-lg-7'
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Style options',
                    Field('fill', css_class='spectrum'), 'fill_opacity', Field('stroke_color', css_class='spectrum'), 'stroke_width', 'stroke_opacity', 'stroke_offset', 'dash_array',
                    active=True
                ),
                AccordionGroup('Advanced options',
                    'gamma', 'gamma_method', 'smooth', 'simplify_tolerance',
                    active=False
                ),
                AccordionGroup('Filter & constraints',
                    'filter', 'minScale', 'maxScale',
                    active=False
                )
            ),
            Div('id', 'DELETE', css_class="hiddenDiv", style="display:none")
        )

    class Meta:
        model = LayerStyle
        fields = ['filter', 'minScale', 'maxScale',
                    'fill', 'fill_opacity', 'stroke_color', 'stroke_width', 'stroke_opacity', 'stroke_offset', 'dash_array',
                    'gamma', 'gamma_method', 'smooth', 'simplify_tolerance'
                    ]


    def clean_dash_array(self):
        data = self.cleaned_data['dash_array']
        if data:
            try:
                data_cleaned = [tuple(float(i) for i in el.strip('()').split(',')) for el in data.split('),(')]
            except:
                raise forms.ValidationError("Except: You must enter tuple(s) of int or float delimited with coma - Ex: (1,1),(2,2)")
        return data

class LayerLabelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.attributes = kwargs.pop("attributes", None)
        super(LayerLabelForm, self).__init__(*args, **kwargs)
        self.fields['field'] = forms.ModelChoiceField(queryset=self.attributes)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.label_class = 'col-lg-5'
        self.helper.field_class = 'col-lg-7'
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup('Style options',
                    'field', 'face_name', Field('fill', css_class='spectrum'), 'size', Field('halo_fill', css_class='spectrum'), 'halo_radius', 'halo_rasterizer', 'opacity', 'character_spacing', 'line_spacing', 'text_ratio', 'text_transform',
                    active=True
                ),
                AccordionGroup('Placement options',
                    'label_placement', 'vertical_alignment', 'horizontal_alignment', 'justify_alignment', 'dx', 'dy', 'orientation', 'rotate_displacement', 'label_position_tolerance',
                    'avoid_edges', 'minimum_padding', 'allow_overlap', 'minimum_distance', 'repeat_distance', 'minimum_path_length', 'maximum_angle_char_delta',
                    active=False
                ),
                AccordionGroup('Wrapping options',
                    'wrap_width', 'wrap_character', 'wrap_before',
                    active=False
                ),
                AccordionGroup('Filter & constraints',
                    'filter', 'minScale', 'maxScale',
                    active=False
                )
            ),
            Div('id', 'DELETE', css_class="hiddenDiv", style="display:none")
        )

    class Meta:
        model = LayerLabel
        exclude = ['layerMapOptions']


