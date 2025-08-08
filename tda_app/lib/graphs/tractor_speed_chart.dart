import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import 'package:tda_app/app_state.dart';
import 'package:tda_app/theme/app_theme.dart';

/// A class to configure each line/series
class SpeedChartConfig<T> {
  final String name;
  final Color color;
  final ChartValueMapper<T, DateTime> xValueMapper;
  final ChartValueMapper<T, num> yValueMapper;

  SpeedChartConfig({
    required this.name,
    required this.color,
    required this.xValueMapper,
    required this.yValueMapper,
  });
}

class TractorSpeedChart<T> extends StatefulWidget {
  final double height;
  final Color backgroundColor;
  final bool isVisible;
  final String title;
  final int refreshRateMs;
  final int maxDataPoints;
  final double animationDuration;
  final T Function()? dataGenerator;
  final List<T>? dataSource;
  final List<SpeedChartConfig<T>> seriesConfigs;
  final String yAxisTitle;
  final String xAxisTitle;

  const TractorSpeedChart({
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
  
  // get isVisible => false;

  @override
  _TractorSpeedChartState<T> createState() => _TractorSpeedChartState<T>();
}

class _TractorSpeedChartState<T> extends State<TractorSpeedChart<T>> {
  late List<T> _chartData;
  final List<ChartSeriesController?> _seriesControllers = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();

    if (widget.dataSource != null) {
      _chartData = widget.dataSource!;
    }
    else if (widget.dataGenerator != null){
      _chartData = [widget.dataGenerator!()];
      _seriesControllers.length = widget.seriesConfigs.length;

      _timer = Timer.periodic(
        Duration(milliseconds: widget.refreshRateMs),
        _updateData,
      );
    }
    else{
      _chartData = [];
    }

  }

  @override
  void didUpdateWidget(covariant TractorSpeedChart<T> oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.dataGenerator == null && widget.dataSource != null) {
      setState(() {
        _chartData = List.from(widget.dataSource!);
      });
    }
  }

  void _updateData(Timer timer) {
    if (widget.dataGenerator == null) return;
    
    final newData = widget.dataGenerator!();

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
    return Consumer<AppState>(
      builder: (context, appstate, child) {
        final data = appstate.tractorSpeedData;
        return Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Chart Header
              Row(
                children: [
                  const Icon(
                    Icons.show_chart,
                    color: AppTheme.accentColor,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'DAQ Chart',
                    // style: Theme.of(context).textTheme.headlineSmall,
                    style: TextStyle(color: AppTheme.textPrimary, fontSize: 20)
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: appstate.isDAQConnected
                          ? AppTheme.successColor.withOpacity(0.2)
                          : AppTheme.textSecondary.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: appstate.isDAQConnected
                            ? AppTheme.successColor
                            : AppTheme.textSecondary,
                        width: 1,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: appstate.isDAQConnected 
                                ? AppTheme.successColor
                                : AppTheme.textSecondary,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          appstate.isDAQConnected ? 'Connected' : 'Disconnected',
                          style: TextStyle(
                            fontSize: 12,
                            color: appstate.isDAQConnected 
                                ? AppTheme.successColor
                                : AppTheme.textSecondary,
                            fontWeight: FontWeight.w500,
                            ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 16),
              
              // Chart Area
              Expanded(
                child: appstate.isDAQConnected
                    ? _buildChart(context, appstate)
                    : _buildPlaceholder(context),
              ),


            ],
          ),
        );
      },
    );
  }

  Widget _buildChart(BuildContext context, AppState appstate) {
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

  Widget _buildPlaceholder(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.stacked_line_chart,
            size: 64,
            color: AppTheme.textSecondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'Connect to an NI Module to view live data',
            style: TextStyle(
              color: AppTheme.textSecondary.withOpacity(0.8),
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Select a Sampling Rate (Hz) then click Start DAQ',
            style: TextStyle(
              color: AppTheme.textSecondary.withOpacity(0.6),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

}
