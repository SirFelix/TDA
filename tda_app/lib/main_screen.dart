// import 'package:accordion/controllers.dart';
// import 'package:get/get.dart';
// import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_slider_drawer/flutter_slider_drawer.dart';
import 'package:tda_app/tabs/dashboard.dart';
import 'package:tda_app/widgets/accordion.dart';
// import 'package:tda_app/widgets/sensor_metric_card.dart';
// import 'package:tda_app/main.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
   final GlobalKey<SliderDrawerState> _sliderDrawerKey =
      GlobalKey<SliderDrawerState>();

  
  
  bool _isDrawerOpen = false;

@override
void initState() {
  super.initState();


  // Used to determine the state of the drawer (_isDrawerOpen) ...
  // ... to animate the tabController to adjust its size accordingly
  WidgetsBinding.instance.addPostFrameCallback((_) {
    final drawerState = _sliderDrawerKey.currentState;
    if (drawerState != null) {
      drawerState.animationController.addStatusListener((status) {
        // Detect when animation starts opening or closing
        if (status == AnimationStatus.forward) {
          setState(() {_isDrawerOpen = true;});
        } else if (status == AnimationStatus.reverse) {
          setState(() {_isDrawerOpen = false;});
        }
        // Detect when animation finishes opening or closing
        if (status == AnimationStatus.completed || status == AnimationStatus.dismissed) {
          final isOpen = drawerState.isDrawerOpen;
          print('Drawer is now ${isOpen ? "open" : "closed"}');
          setState(() {_isDrawerOpen = isOpen;});
        }
      });
    }
  });
}




  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SliderDrawer(
        isDraggable: false,
        key: _sliderDrawerKey,
        appBar: SliderAppBar(
          config: SliderAppBarConfig(
            backgroundColor: Colors.blue[700],
            title: AnimatedPadding(
              curve: Curves.decelerate,
              padding: EdgeInsets.only(right: _isDrawerOpen ? 300 : 0),
              duration: Duration(milliseconds: _isDrawerOpen ? 400 : 600),
              child: Text('Tractor Data Analyzer',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color.fromARGB(230, 255, 255, 255),
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ),
        sliderOpenSize: 320,
        slider: ControlPanelAccordion(),
        child: TabController(isDrawerOpen: _isDrawerOpen,),

      ),
    );
  }
}





class TabController extends StatefulWidget {
  final bool isDrawerOpen;

  const TabController({
    super.key,
    required this.isDrawerOpen,
  });

  @override
  State<TabController> createState() => _TabControllerState();
}

class _TabControllerState extends State<TabController> {

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 1,
      child: AnimatedPadding(
        curve: Curves.decelerate,
        // reverseCurve: Curves.decelerate,
        // duration: duration,
        duration: Duration(milliseconds: widget.isDrawerOpen ? 400 : 600),
        padding: EdgeInsets.only(right: widget.isDrawerOpen ? 300 : 0),
        child: Scaffold(
          appBar: PreferredSize(
            preferredSize: const Size.fromHeight(kToolbarHeight - 8),
            child: AppBar(
              bottom: const TabBar(
                tabs: [
                  Tab(icon: Icon(Icons.stacked_line_chart_outlined)),
                  // Tab(icon: Icon(Icons.settings)),
                  // Tab(icon: Icon(Icons.person_2)),
                ],
              ),
            ),
          ),
          body: TabBarView(
            children: [
              // Container(
              //   padding: const EdgeInsets.all(16), 
              // ),
              const DashboardTab(),
              // Center(child: Text('Tab 2')),
              // Center(child: Text('Tab 3')),
            ],
          ),
        ),
      ),
    );
  }
}

