import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import '../theme/app_theme.dart';

class GenericChartWidget<T> extends StatelessWidget {
  final bool isConnected;
  final String title;
  final IconData icon;
  final List<T> data;
  final ChartValueMapper<T, DateTime> xValueMapper;
  final ChartValueMapper<T, num> yValueMapper;
  final String placeholderTitle;
  final String placeholderHint;

  const GenericChartWidget({
    super.key,
    required this.isConnected,
    required this.title,
    required this.icon,
    required this.data,
    required this.xValueMapper,
    required this.yValueMapper,
    required this.placeholderTitle,
    required this.placeholderHint,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          const SizedBox(height: 16),
          Expanded(
            child: isConnected && data.isNotEmpty
              ? _buildChart()
              : _buildPlaceholder(),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Icon(icon, color: AppTheme.accentColor, size: 20),
        const SizedBox(width: 8),
        Text(title, style: TextStyle(color: AppTheme.textPrimary, fontSize: 20)),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: isConnected
                ? AppTheme.successColor.withOpacity(0.2)
                : AppTheme.textSecondary.withOpacity(0.2),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isConnected ? AppTheme.successColor : AppTheme.textSecondary,
              width: 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: isConnected ? AppTheme.successColor : AppTheme.textSecondary,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                isConnected ? 'Connected' : 'Disconnected',
                style: TextStyle(
                  fontSize: 12,
                  color: isConnected ? AppTheme.successColor : AppTheme.textSecondary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildChart() {
    return SfCartesianChart(
      backgroundColor: Colors.transparent,
      plotAreaBorderWidth: 0,
      zoomPanBehavior: ZoomPanBehavior(
        enablePanning: true,
        enableMouseWheelZooming: true,
      ),
      primaryXAxis: DateTimeAxis(
        axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
      ),
      primaryYAxis: NumericAxis(
        axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
      ),
      series: <CartesianSeries>[
        LineSeries<T, DateTime>(
          dataSource: data,
          xValueMapper: xValueMapper,
          yValueMapper: yValueMapper,
          color: AppTheme.accentColor,
          width: 2,
          animationDuration: 0,
        ),
      ],
      tooltipBehavior: TooltipBehavior(
        enable: true,
        color: AppTheme.surfaceColor,
        textStyle: const TextStyle(color: AppTheme.textPrimary),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.timeline_outlined, size: 64, color: AppTheme.textSecondary.withOpacity(0.5)),
          const SizedBox(height: 16),
          Text(
            placeholderTitle,
            style: TextStyle(color: AppTheme.textSecondary.withOpacity(0.8), fontSize: 16),
          ),
          const SizedBox(height: 8),
          Text(
            placeholderHint,
            style: TextStyle(color: AppTheme.textSecondary.withOpacity(0.6), fontSize: 12),
          ),
        ],
      ),
    );
  }
}
