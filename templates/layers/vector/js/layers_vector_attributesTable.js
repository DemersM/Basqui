var dataView;
var grid;
var checkboxSelector = new Slick.CheckboxSelectColumn({
  cssClass: "slick-cell-checkboxsel"
});
var columns = [ checkboxSelector.getColumnDefinition(),
  { id: "id", name: "ID", field: "id", resizable: false, width: 50, sortable: true, sorter: sorterNumeric,
      formatter: linkFormatter = function ( row, cell, value, columnDef, dataContext ) {
            return '<a href="javascript:void(0)" onclick="initLightViewer('+row+','+value+')">' + value + '</a>';
      }
  },
{% for column in columns %}
  {id: '{{ column.name }}', field: '{{ column.name }}', sortable: true, width: 120,
    {% if column.type == 0 %} 
      name: '{{ column.name }}<span class="column-type">Integer ({{ column.width }})</span>', 
      sorter: sorterNumeric,
      editor: Slick.Editors.Integer,
    {% elif column.type == 2 %}
      name: '{{ column.name }}<span class="column-type">Float ({{ column.width }}, {{ column.precision }})</span>', 
      sorter: sorterNumeric,
      editor: Slick.Editors.Text,
    {% elif column.type == 4 %}
      name: '{{ column.name }}<span class="column-type">String ({{ column.width }})</span>',
      sorter: sorterStringCompare,
      {% if column.width > 10 %}editor: Slick.Editors.LongText,{% else %} editor: Slick.Editors.Text,{% endif %}
    {% elif column.type == 9 %}
      name: '{{ column.name }}<span class="column-type">Date</span>',
      sorter: sorterDateIso, 
      editor: Slick.Editors.Date,
    {% else %}
      name: '{{ column.name }}<span class="column-type">Time</span>',
      sorter: sorterStringCompare,
      editor: Slick.Editors.Text,
    {% endif %}
  },
{% endfor %}];

var columnFilters = {};
var commandQueue = [];
var redocommandQueue = [];

var options = {
  editable: true,
  enableCellNavigation: true,
  enableColumnReorder: true,
  multiColumnSort: true,
  showHeaderRow: true,
  headerRowHeight: 29,
  editCommandHandler: queueAndExecuteCommand,
  autoEdit: false,
  explicitInitialization: true,
};

window.initLightViewer = function(row, value){
  grid.setActiveCell(row, 1)
  position = grid.getActiveCellPosition()
  $.ajax({
    type: "POST",
    url: "/basqui/layer/shapefile/attributesTable/{{ layer.pk }}/lightViewer/",
    data: {'position': position, 'id': value}, dataType: "json",
    success: function(r) {
      showLightViewer(r['feat_id'], r['x'], r['y'], r['bounds'], value)
    }
 });
}

function updateAttributeTable(e,args) {
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ layer.pk }}/update/",
      data: args.item, dataType: "json",
      success: function(r) {
                  if(r['error']) {
                       $("#saved").empty();
                       $("#error").text(r['error']);
                       grid.flashCell(args.row, args.cell, 400);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(r['saved']);
                       dataView.updateItem(args.item.id, r['data']);
                       grid.invalidateRow(args.row);
                       grid.render();
                  }
                },
       });
}

window.addFeatureToTable = function() {
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ layer.pk }}/addFeature/",
      success: function(r) {
                  if(r['error']) {
                       $("#saved").empty();
                       $("#error").text(r['error']);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(r['saved']);
                         dataView.beginUpdate();
                         dataView.addItem(r['data']);
                         dataView.endUpdate();
                         rowCount = dataView.getLength();
                         $("div.dataGrid").css("height", '+=25px');
                         grid.resizeCanvas();
                         grid.scrollRowIntoView(rowCount);
                         $("#FeatCount").text(rowCount + " features");
                  }
                },
       });
}

window.deleteRow = function() {
  var rows_id = grid.getSelectedRows();
  var feat_id = [];
  for (var i=0; i < rows_id.length; i++) {
    var id = grid.getDataItem(rows_id[i]).id
    feat_id.push(id);
  };
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ layer.pk }}/deleteFeature/",
      data: {"feat_id" : feat_id}, dataType: "json",
      success: function(r) {
                  if(r['error']) {
                       $("#saved").empty();
                       $("#error").text(r['error']);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(r['saved']);
                       dataView.beginUpdate();
                       for (var i=0; i < feat_id.length; i++) {
                         dataView.deleteItem(feat_id[i]);
                       }
                       dataView.endUpdate();
                       grid.setSelectedRows([]);
                       rowCount = dataView.getLength();
                       $("div.dataGrid").css("height", rowCount*25+74);
                       grid.resizeCanvas();
                       grid.render();
                       $("#FeatCount").text(rowCount + " features");
                  }
                },
       });
}

function queueAndExecuteCommand(item, column, editCommand) {
    commandQueue.push(editCommand);
    editCommand.execute();
  }

window.undo = function() {
    var command = commandQueue.pop();
    redocommandQueue.push(command);
    if (command && Slick.GlobalEditorLock.cancelCurrentEdit()) {
        command.undo();
        grid.gotoCell(command.row,command.cell,true);
    }
}

window.redo = function() {
  var redocommand = redocommandQueue.pop();
  if (redocommand && Slick.GlobalEditorLock.cancelCurrentEdit()) {
    commandQueue.push(redocommand);
    redocommand.execute();
    grid.gotoCell(redocommand.row,redocommand.cell,true);
  }
}

function sorterStringCompare(a, b) {
  var x = a[sortcol], y = b[sortcol];
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterNumeric(a, b) {
  var x = (isNaN(a[sortcol]) || a[sortcol] === "" || a[sortcol] === null) ? -99e+10 : parseFloat(a[sortcol]);
  var y = (isNaN(b[sortcol]) || b[sortcol] === "" || b[sortcol] === null) ? -99e+10 : parseFloat(b[sortcol]);
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterRating(a, b) {
  var xrow = a[sortcol], yrow = b[sortcol];
  var x = xrow[3], y = yrow[3];
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterDateIso(a, b) {
  var regex_a = new RegExp("^((19[1-9][1-9])|([2][01][0-9]))\\d-([0]\\d|[1][0-2])-([0-2]\\d|[3][0-1])(\\s([0]\\d|[1][0-2])(\\:[0-5]\\d){1,2}(\\:[0-5]\\d){1,2})?$", "gi");
  var regex_b = new RegExp("^((19[1-9][1-9])|([2][01][0-9]))\\d-([0]\\d|[1][0-2])-([0-2]\\d|[3][0-1])(\\s([0]\\d|[1][0-2])(\\:[0-5]\\d){1,2}(\\:[0-5]\\d){1,2})?$", "gi");

  if (regex_a.test(a[sortcol]) && regex_b.test(b[sortcol])) {
    var date_a = new Date(a[sortcol]);
    var date_b = new Date(b[sortcol]);
    var diff = date_a.getTime() - date_b.getTime();
    return sortdir * (diff === 0 ? 0 : (date_a > date_b ? 1 : -1));
  }
  else {
    var x = a[sortcol], y = b[sortcol];
    return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
  }
}

$(document).ready(function () {
  function filter(item) {
    for (var columnId in columnFilters) {
      if (columnId !== undefined && columnFilters[columnId] !== "") {
        var c = grid.getColumns()[grid.getColumnIndex(columnId)];
        if (item[c.field] != columnFilters[columnId]) {
          return false;
        }
      }
    }
    return true;
  }

  dataView = new Slick.Data.DataView();
  grid = new Slick.Grid(".dataGrid", dataView, columns, options);
  grid.setSelectionModel(new Slick.RowSelectionModel({selectActiveRow: false}));
  grid.registerPlugin(checkboxSelector);

  var columnpicker = new Slick.Controls.ColumnPicker(columns, grid, options);
;

  $(function () {

    dataView.onRowCountChanged.subscribe(function (e, args) {
      grid.updateRowCount();
      grid.render();
    });

    dataView.onRowsChanged.subscribe(function (e, args) {
      grid.invalidateRows(args.rows);
      grid.render();
    });


    $(grid.getHeaderRow()).delegate(":input", "change keyup", function (e) {
      var columnId = $(this).data("columnId");
      if (columnId != null) {
        columnFilters[columnId] = $.trim($(this).val());
        dataView.refresh();
      }
    });

    grid.onCellChange.subscribe(function (e, args) {
      updateAttributeTable(e, args);
    });

    grid.onHeaderRowCellRendered.subscribe(function(e, args) {
      $(args.node).empty();
      $("<input type='text'>")
        .data("columnId", args.column.id)
        .val(columnFilters[args.column.id])
        .appendTo(args.node);
    });

    grid.init();

    $.ajax({
          type: "GET",
          url: "/basqui/layer/shapefile/attributesTable/loader/{{ layer.pk }}/",
          success: function(r) {
                      dataView.beginUpdate();
                      dataView.setItems(r);
                      dataView.setFilter(filter);
                      dataView.endUpdate();
                    },
    });



  })

  grid.onColumnsResized.subscribe(function(e,args) {
    var columns = grid.getColumns();
    var columnsWidth = -2;
    for (var x in columns){
        columnsWidth += columns[x].width;
        console.log(columns[x]);
    };
    $(".grid-header").width(columnsWidth);
    $(".grid-footer").width(columnsWidth);
   });

  grid.onSort.subscribe(function (e, args) {
    var cols = args.sortCols;

    dataView.sort(function (dataRow1, dataRow2) {
      for (var i = 0, l = cols.length; i < l; i++) {
        sortdir = cols[i].sortAsc ? 1 : -1;
        sortcol = cols[i].sortCol.field;

        var result = cols[i].sortCol.sorter(dataRow1, dataRow2);
        if (result != 0) {
          return result;
          }
        }
        return 0;
      });
      args.grid.invalidateAllRows();
      args.grid.render();
  });
});

Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'Ext.window.MessageBox',
    'Ext.window.Window',
    'GeoExt.panel.Map'
]);

Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
      expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
}));

function showLightViewer(feat_id, pos_x, pos_y, bounds, value){
  var map = new OpenLayers.Map('map',
            { projection: new OpenLayers.Projection("EPSG:3857"),
              numZoomLevels: 20,
              });

  var tiledLayer = new OpenLayers.Layer.CustomXYZ('TMS',
    "{{ tmsURL }}1.0/feature/{{ layer.pk }}/" + feat_id + "/${z}/${x}/${y}.png");

  map.addLayer(tiledLayer);
  
  map.size = new OpenLayers.Size(200,200);
  var bounds = new OpenLayers.Bounds.fromArray(bounds);
  map.zoomToExtent(bounds);
  
  var geoExtPanel = Ext.create('GeoExt.panel.Map', {
      map: map,
      border: 0,
  });
  
  var mapWin = Ext.create('Ext.window.Window', {
    title: "Layer: {{ layer.filename }} | Feature: " + value, 
    x: pos_x,
    y: pos_y,
    height: 250,
    width: 250,
    layout: 'fit',
    items: [
       geoExtPanel
    ],
    collapsible: true,
    bodyBorder: false,
    renderTo: Ext.getBody(),
  }).show();
}