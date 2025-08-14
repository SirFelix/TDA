import 'dart:async';
import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import 'package:tda_app/theme/app_theme.dart';

/// A class to configure each line/series
class ChartSeriesConfig<T> {
  final String name;
  final Color color;
  final ChartValueMapper<T, DateTime> xValueMapper;
  final ChartValueMapper<T, num> yValueMapper;

  ChartSeriesConfig({
    required this.name,
    required this.color,
    required this.xValueMapper,
    required this.yValueMapper,
  });
}

class DaqChartWidget<T> extends StatefulWidget {
  final double height;
  final Color backgroundColor;
  final bool isVisible;
  final String title;
  final int refreshRateMs;
  final int maxDataPoints;
  final double animationDuration;
  final T Function()? dataGenerator;
  final List<T>? dataSource;
  final List<ChartSeriesConfig<T>> seriesConfigs;
  final String yAxisTitle;
  final String xAxisTitle;

  const DaqChartWidget({
    super.key,
    this.height = 300,
    this.backgroundColor = Colors.white,
    this.title = 'Sensor Data',
    this.refreshRateMs = 500,
    this.maxDataPoints = 200,
    this.animationDuration = 0,
    this.dataGenerator,
    this.dataSource,
    required this.seriesConfigs,
    this.yAxisTitle = 'Value',
    this.xAxisTitle = 'Time',
    this.isVisible = false,
  });

  @override
  _DaqChartWidgetState<T> createState() => _DaqChartWidgetState<T>();
}

class _DaqChartWidgetState<T> extends State<DaqChartWidget<T>> {
  /// Internal chart list used for generator mode.
  /// When dataSource is supplied we avoid mutating the caller's list:
  /// we copy it into [_chartDataSnapshot] for rendering and tracking.
  List<T> _chartDataSnapshot = <T>[];

  final List<ChartSeriesController?> _seriesControllers = [];
  Timer? _timer;

  bool get usingSource => widget.dataSource != null;
  bool get usingGenerator => widget.dataGenerator != null;

  @override
  void initState() {
    super.initState();

    // Ensure controller list has the right length
    _seriesControllers.length = widget.seriesConfigs.length;

    if (usingSource) {
      // copy initial data snapshot (do not alias)
      _chartDataSnapshot = List<T>.from(widget.dataSource!);
    } else if (usingGenerator) {
      // seed with one generated point so the chart has something initially
      _chartDataSnapshot = [widget.dataGenerator!()];
      _timer = Timer.periodic(
        Duration(milliseconds: widget.refreshRateMs),
        _updateData,
      );
    } else {
      _chartDataSnapshot = <T>[];
    }
  }

  @override
  void didUpdateWidget(covariant DaqChartWidget<T> oldWidget) {
    super.didUpdateWidget(oldWidget);

    // If we switched to using a dataSource (or the dataSource changed), copy it
    if (widget.dataSource != null) {
      // Copy the incoming list so we don't mutate external references
      setState(() {
        _chartDataSnapshot = List<T>.from(widget.dataSource!);
      });
    } else if (widget.dataGenerator != null && oldWidget.dataGenerator == null) {
      // If generator was newly provided, start timer (if not already)
      _timer?.cancel();
      _chartDataSnapshot = [widget.dataGenerator!()];
      _timer = Timer.periodic(
        Duration(milliseconds: widget.refreshRateMs),
        _updateData,
      );
    } else if (widget.dataGenerator == null && oldWidget.dataGenerator != null) {
      // If generator removed, cancel timer
      _timer?.cancel();
    }

    // Ensure series controllers list length matches seriesConfigs length
    if (_seriesControllers.length != widget.seriesConfigs.length) {
      _seriesControllers.length = widget.seriesConfigs.length;
    }
  }

void _updateData(Timer timer) {
  // If the widget has been disposed, Stop doing work.
  if (!mounted) {
    timer.cancel();
    return;
  }

  if (!usingGenerator) return;
  final newData = widget.dataGenerator!();

  // Update internal snapshot
  setState(() {
    _chartDataSnapshot.add(newData);
    if (_chartDataSnapshot.length > widget.maxDataPoints) {
      _chartDataSnapshot.removeAt(0);
    }
  });

  // Update series controllers safely
  for (int i = 0; i < _seriesControllers.length; i++) {
    final ctrl = _seriesControllers[i];
    if (ctrl == null) continue;
    try {
      ctrl.updateDataSource(
        addedDataIndexes: <int>[_chartDataSnapshot.length - 1],
        removedDataIndexes:
            _chartDataSnapshot.length > widget.maxDataPoints ? <int>[0] : null,
      );
    } catch (err, st) {
      // Defensive: swallow errors that happen because the chart was disposed
      // during a hot reload/navigation. Optionally log in debug mode:
      assert(() {
        // ignore: avoid_print
        print('Warning: controller update failed (probably disposed): $err\n$st');
        return true;
      }());
    }
  }
}


@override
void dispose() {
  _timer?.cancel();
  // Optionally clear controllers
  for (int i = 0; i < _seriesControllers.length; i++) {
    _seriesControllers[i] = null;
  }
  super.dispose();
}


  Widget _buildWaitingForData(BuildContext context) {
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: widget.backgroundColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderColor),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.hourglass_top, size: 40, color: Colors.grey),
            SizedBox(height: 10),
            Text(
              'Waiting for data…',
              style: TextStyle(fontSize: 16, color: Colors.grey),
            ),
            SizedBox(height: 6),
            Text(
              'No data available yet. Connect your DAQ or start streaming.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // If using a dataSource and it's empty -> show waiting UI
    if (usingSource && (widget.dataSource!.isEmpty)) {
      return _buildWaitingForData(context);
    }

    // Otherwise render the chart using the snapshot (either generator-mode snapshot
    // or the copied dataSource snapshot).
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: widget.backgroundColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderColor),
      ),
      child: SfCartesianChart(
        zoomPanBehavior: ZoomPanBehavior(
          enablePanning: true,
          enableSelectionZooming: true,
        ),
        primaryXAxis: DateTimeAxis(
          majorGridLines:
              const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
          labelStyle:
              const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
        ),
        primaryYAxis: NumericAxis(
          majorGridLines:
              const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
          labelStyle:
              const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
          // If you want to remove forced min, comment it out or expose a prop to set it.
          // minimum: 0,
        ),
        legend: Legend(
          isVisible: widget.isVisible,
          toggleSeriesVisibility: true,
          position: LegendPosition.top,
          offset: const Offset(0, 0),
          alignment: ChartAlignment.far,
          overflowMode: LegendItemOverflowMode.none,
          isResponsive: true,
        ),
        series: List<LineSeries<T, DateTime>>.generate(
          widget.seriesConfigs.length,
          (i) {
            final config = widget.seriesConfigs[i];
            return LineSeries<T, DateTime>(
              animationDuration: widget.animationDuration,
              onRendererCreated: (controller) {
                // store controller in array (safe even if length changed)
                if (i >= _seriesControllers.length) {
                  // expand if needed
                  _seriesControllers.length = widget.seriesConfigs.length;
                }
                _seriesControllers[i] = controller;
              },
              dataSource: _chartDataSnapshot,
              xValueMapper: config.xValueMapper,
              yValueMapper: config.yValueMapper,
              color: config.color,
              name: config.name,
            );
          },
        ),
      ),
    );
  }
}
