var dataView;
var grid;
var checkboxSelector = new Slick.CheckboxSelectColumn({
  cssClass: "slick-cell-checkboxsel"
});
var columns = [ checkboxSelector.getColumnDefinition(),
  { id: "id", name: "ID", field: "id", resizable: false, width: 50, sortable: true, sorter: sorterNumeric,
      formatter: linkFormatter = function ( row, cell, value, columnDef, dataContext ) {
            return '<a href="/basqui/layer/shapefile/edit/{{ shapefile.pk }}/' + dataContext['id'] + '">' + value + '</a>';
      }
  },
];

var columnFilters = {};
var commandQueue = [];
var redocommandQueue = [];

var options = {
  editable: true,
  enableCellNavigation: true,
  enableColumnReorder: true,
  multiColumnSort: true,
  showHeaderRow: true,
  headerRowHeight: 30,
  editCommandHandler: queueAndExecuteCommand,
  autoEdit: false,
  explicitInitialization: true,
};

//var data = {{ data|safe }}

function updateAttributeTable(e,args) {
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ shapefile.pk }}/update/",
      data: args.item, dataType: "json",
      success: function(a) {
                  if(a['error']) {
                       $("#saved").empty();
                       $("#error").text(a['error']);
                       grid.flashCell(args.row, args.cell, 400);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(a[0]['saved']);
                       dataView.updateItem(args.item.id, a[1]);
                       dataView.setHighlightedCells(args.row, args.cell)
                       grid.invalidateRow(args.row);
                       grid.render();
                  }
                },
       });
}

window.addFeatureToTable = function() {
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ shapefile.pk }}/addFeature/",
      success: function(a) {
                  if(a['error']) {
                       $("#saved").empty();
                       $("#error").text(a['error']);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(a[0]['saved']);
                         dataView.beginUpdate();
                         dataView.addItem(a[1]);
                         dataView.endUpdate();
                         rowCount = dataView.getLength();
                         $("div.dataGrid").css("height", rowCount*25+60);
                         grid.resizeCanvas();
                         grid.scrollRowIntoView(rowCount);
                         $("#FeatCount").text(rowCount + " features");
                  }
                },
       });
}

window.deleteRow = function() {
  rows_id = grid.getSelectedRows();
  feat_id = [];
  for (var i=0; i < rows_id.length; i++) {
    var id = grid.getDataItem(rows_id[i]).id
    feat_id.push(id);
  };
  $.ajax({
      type: "POST",
      url: "/basqui/layer/shapefile/attributesTable/{{ shapefile.pk }}/deleteFeature/",
      data: {"feat_id" : feat_id}, dataType: "json",
      success: function(a) {
                  if(a['error']) {
                       $("#saved").empty();
                       $("#error").text(a['error']);
                  }
                  else {
                       $("#error").empty();
                       $("#saved").text(a['saved']);
                       dataView.beginUpdate();
                       for (var i=0; i < feat_id.length; i++) {
                         dataView.deleteItem(feat_id[i]);
                       }
                       dataView.endUpdate();
                       grid.setSelectedRows([]);
                       rowCount = dataView.getLength();
                       $("div.dataGrid").css("height", rowCount*25+60);
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
