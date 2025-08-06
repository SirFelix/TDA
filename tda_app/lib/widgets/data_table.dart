import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_datagrid/datagrid.dart';


class DataLogInputTable extends StatefulWidget {
  const DataLogInputTable({super.key});

  @override
  State<DataLogInputTable> createState() => _DataLogInputTableState();
}

class _DataLogInputTableState extends State<DataLogInputTable> {
  late DataInputDataSource _dataSource;

  @override
  void initState() {
    super.initState();
    _dataSource = DataInputDataSource();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 100,
      child: SfDataGrid(
        source: _dataSource,
        allowEditing: true,
        frozenRowsCount: 1,
        columnWidthMode: ColumnWidthMode.fill,
        navigationMode: GridNavigationMode.cell,
        selectionMode: SelectionMode.single,
        columns: [
          GridColumn(
              columnName: 'Time',
              label: Container(
                  alignment: Alignment.center,
                  padding: const EdgeInsets.all(8),
                  child: const Text('Time'))),
          GridColumn(
              columnName: 'value',
              label: Container(
                  alignment: Alignment.center,
                  padding: const EdgeInsets.all(8),
                  child: const Text('Value'))),
          GridColumn(
              columnName: 'unit',
              label: Container(
                  alignment: Alignment.center,
                  padding: const EdgeInsets.all(8),
                  child: const Text('Unit'))),
        ],
      ),
    );
  }
}


// ------------------------------------------------------------------------------
class DataInputRow {
  String name;
  double value;
  String unit;

  DataInputRow({this.name = '', this.value = 0.0, this.unit = ''});
}

class DataInputDataSource extends DataGridSource {
  List<DataGridRow> _rows = [];
  List<DataInputRow> data = [];

  DataInputDataSource() {
    data = [DataInputRow()];
    _rows = data.map<DataGridRow>((item) {
      return DataGridRow(cells: [
        DataGridCell<String>(columnName: 'name', value: item.name),
        DataGridCell<double>(columnName: 'value', value: item.value),
        DataGridCell<String>(columnName: 'unit', value: item.unit),
      ]);
    }).toList();
  }

  @override
  List<DataGridRow> get rows => _rows;

  @override
  DataGridRowAdapter buildRow(DataGridRow row) {
    return DataGridRowAdapter(
      cells: row.getCells().map<Widget>((cell) {
        return TextField(
          controller: TextEditingController(text: cell.value.toString()),
          decoration: const InputDecoration(border: InputBorder.none),
          onChanged: (val) {
            // Update underlying model (optional for now)
          },
        );
      }).toList(),
    );
  }

  void handleSaveCell(DataGridRow row, RowColumnIndex columnIndex, GridColumn column, dynamic newValue) {
    final int rowIndex = _rows.indexOf(row);
    final String columnName = column.columnName;

    switch (columnName) {
      case 'name':
        data[rowIndex].name = newValue.toString();
        break;
      case 'value':
        data[rowIndex].value = double.tryParse(newValue.toString()) ?? 0.0;
        break;
      case 'unit':
        data[rowIndex].unit = newValue.toString();
        break;
    }

    // Rebuild rows to reflect updates
    _rows = DataInputRow() as List<DataGridRow>;
    notifyListeners();
  }


}
