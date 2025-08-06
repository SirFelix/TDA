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
  final T Function() dataGenerator;
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
    required this.dataGenerator,
    required this.seriesConfigs,
    this.yAxisTitle = 'Value',
    this.xAxisTitle = 'Time',
    this.isVisible = false,
  });
  
  // get isVisible => false;

  @override
  _DaqChartWidgetState<T> createState() => _DaqChartWidgetState<T>();
}

class _DaqChartWidgetState<T> extends State<DaqChartWidget<T>> {
  late List<T> _chartData;
  final List<ChartSeriesController?> _seriesControllers = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _chartData = [widget.dataGenerator()];
    _seriesControllers.length = widget.seriesConfigs.length;

    _timer = Timer.periodic(
      Duration(milliseconds: widget.refreshRateMs),
      _updateData,
    );
  }

  void _updateData(Timer timer) {
    final newData = widget.dataGenerator();

    setState(() {
      _chartData.add(newData);
      if (_chartData.length > widget.maxDataPoints) {
        _chartData.removeAt(0);
      }
    });

    for (int i = 0; i < _seriesControllers.length; i++) {
      _seriesControllers[i]?.updateDataSource(
        addedDataIndexes: <int>[_chartData.length - 1],
        removedDataIndexes:
            _chartData.length > widget.maxDataPoints ? <int>[0] : null,
      );
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: widget.height,
      color: widget.backgroundColor,
      padding: const EdgeInsets.all(8),
      child: SfCartesianChart(
        zoomPanBehavior: ZoomPanBehavior(enableMouseWheelZooming: true, enablePanning: true, enableSelectionZooming: true,),
        
        primaryXAxis: DateTimeAxis(
        // axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
        ),

        primaryYAxis: NumericAxis(
        // axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
        
        ),

        // title: ChartTitle(text: widget.title),

        // primaryXAxis: DateTimeAxis(title: AxisTitle(text: widget.xAxisTitle)),
        // primaryYAxis: NumericAxis(title: AxisTitle(text: widget.yAxisTitle)),

        // legend: Legend(isVisible: widget.isVisible, toggleSeriesVisibility: true, position: LegendPosition.bottom, offset: const Offset(0, -45), // For inside the bottom right of the graph
        legend: Legend(isVisible: widget.isVisible, toggleSeriesVisibility: true, position: LegendPosition.top, offset: const Offset(0, 0), // For inside the top right of the graph
          alignment: ChartAlignment.far, overflowMode: LegendItemOverflowMode.none, isResponsive: true),
        series: List<LineSeries<T, DateTime>>.generate(
          widget.seriesConfigs.length,
          (i) {
            final config = widget.seriesConfigs[i];
            return LineSeries<T, DateTime>(
              animationDuration: widget.animationDuration,
              onRendererCreated: (controller) => _seriesControllers[i] = controller,
              dataSource: _chartData,
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
