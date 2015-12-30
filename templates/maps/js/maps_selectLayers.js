Ext.define('Folder', {
    extend: 'Ext.data.Model',
    fields: [
        { name: 'id', type: 'int' },
        { name: 'name', type: 'string' },
        { name: 'type', type: 'string' }
    ],
    proxy: {
            type: 'ajax',
            url: "{% url 'trees:maps_selectLayersTree' map_id %}",
    }
});

var store = Ext.create('Ext.data.TreeStore', {
  model: 'Folder',
  root: {'name' : 'Layers',
         'id' : '{{ folder.pk }}',
         'type' : '{{ folder.type }}',
         'expanded': true,
  }
});

var selectLayersTree =  Ext.create('Ext.tree.Panel', {
    useArrows: true,
    rootVisible: true,
    store: store,
    columns: [
          { xtype: 'treecolumn', header: 'Name', dataIndex: 'name', flex:2 },
          { text: 'Id', 'dataIndex': 'id', flex:1, sortable: true },
          { text: 'Type', 'dataIndex': 'type', flex:1, sortable: true },
    ],
    tbar: [{
      html: '<span class="glyphicon glyphicon-folder-open" aria-hidden="true"></span>',
      handler: function(){
                selectLayersTree.expandAll();
              }
      }, {
      html: '<span class="glyphicon glyphicon-folder-close" aria-hidden="true"></span>',
      handler: function(){
                selectLayersTree.collapseAll();
              }
      }, {
      html: '<span class="glyphicon glyphicon-floppy-disk" aria-hidden="true"></span>',
      handler: function(){
          var records = selectLayersTree.getView().getChecked(),
              layers_ids = [];
          Ext.Array.each(records, function(rec){
              layers_ids.push(rec.get('id'));
          });

          Ext.Ajax.request({
          url: "{% url 'maps:saveSelectedLayers' map_id %}",
          method: "POST",
          params: {'layers_ids' : layers_ids },
          success : function(r){
                       html = Ext.decode(r.responseText);
                       Ext.get("layerMapOptions").update(html);
                       initLayerMapOptionsFormset();
                       tiledLayer.redraw(true);
                    }
          });
      }
    }],
});

var selectLayersWin = Ext.create('Ext.window.Window', {
    title: "Select map's layer(s)",
    id: 'selectLayersWin',
    x: 350,
    y: 175,
    height: 600,
    width: 400,
    minWidth: 400,
    layout: 'fit',
    collapsible: true,
    bodyStyle: 'background:#fff; border:0px; padding:0px;',
    bodyBorder: false,
    autoScroll: true,
    closeAction: 'destroy',
    items: selectLayersTree,
    renderTo: Ext.getBody()
}).show();
