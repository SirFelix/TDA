import 'package:flutter/material.dart';
import 'package:accordion/accordion.dart';
import 'package:tda_app/dropdowns/daq_dropdown.dart';
import 'package:tda_app/dropdowns/log_dropdown.dart';
import 'package:tda_app/dropdowns/rig_dropdown.dart';
import 'package:tda_app/dropdowns/ws_dropdown.dart';

class ControlPanelAccordion extends StatelessWidget {
  const ControlPanelAccordion({super.key});

  static const headerStyle = TextStyle(color: Color(0xffffffff), fontSize: 16, fontWeight: FontWeight.bold);
  static const contentStyleHeader = TextStyle(color: Color(0xff999999), fontSize: 14, fontWeight: FontWeight.w700);
  static const contentStyle = TextStyle(color: Color.fromARGB(255, 153, 153, 153), fontSize: 14, fontWeight: FontWeight.normal);

  @override
  Widget build(BuildContext context) { // Changed build method return type to Widget
    return Container(
      // Background color of the slider drawer
      color: Colors.white60,
      width: double.infinity,
      child: Column( // This Column is the main layout container
        children: [
          Container( // Header
            color: Colors.blue[700],
            width: double.infinity,
            height: 56,
            padding: const EdgeInsets.all(10),
            child: const Text(
              'Control Panel',
              style: TextStyle(
                color: Color.fromARGB(255, 227, 227, 227), 
                fontSize: 26, 
                fontWeight: FontWeight.w700
              ),
              textAlign: TextAlign.center,
            ),
          ),
          Expanded(
            child: SingleChildScrollView( // Accordion (takes available space)
              child: Accordion(
                headerBackgroundColor:  Colors.blueGrey,
                headerBackgroundColorOpened:   Colors.blueGrey,
                // headerBackgroundColor:  Colors.deepOrange,
                // headerBackgroundColorOpened:   Color.fromARGB(255, 255, 109, 4),
                // headerBorderColor: Colors.blueGrey,
                // headerBorderColorOpened: Colors.blueGrey,
                contentBorderColor: Colors.transparent,
                headerBorderWidth: 10,
                contentBorderWidth: 4,
                scaleWhenAnimating: true,
                openAndCloseAnimation: true,
                paddingListTop: 0,
                paddingListHorizontal: 0,
                paddingBetweenClosedSections: 0,
                paddingBetweenOpenSections: 0,
                headerBorderRadius: 10,
                contentBorderRadius: 10,
                children: [
                  AccordionSection(
                    leftIcon: const Icon(Icons.settings_applications_sharp, color: Colors.white),
                    header: Center(child: const Text('Connection Settings', style: headerStyle)),
                    content: const WSDropdown(),
                  ),

                  AccordionSection(
                    // isOpen: true,
                    contentVerticalPadding: 0,
                    headerPadding: const EdgeInsets.symmetric(horizontal: 0),
                    leftIcon: const Icon(Icons.electrical_services, color: Colors.white),
                    header: Center(child: const Text('DAQ Config', style: headerStyle)),
                    // content: Text('Content 1', style: contentStyle),
                    content: const DaqDropdown(),
                  ),

                  AccordionSection(
                    leftIcon: const Icon(Icons.insert_chart_outlined_outlined, color: Colors.white),
                    header: Center( child: const Text('Rig Config', style: headerStyle)),
                    content: const RigDropdown(),
                  ),

                  AccordionSection(
                    leftIcon: const Icon(Icons.receipt_long_rounded, color: Colors.white),
                    header: Center(child: const Text('Logging Config', style: headerStyle)),
                    content: const LogDropdown(),
                  ),

                ],
              ),
            ),
          ),

          // // const Spacer(), // Spacer (fills remaining space)
          // Container( // Footer
          //   padding: const EdgeInsets.all(10),
          //   color: Colors.deepOrange,
          //   width: double.infinity,
          //   child: const Text(
          //     'App Settings',
          //     style: TextStyle(color: Color.fromARGB(230, 255, 255, 255), fontWeight: FontWeight.bold),
          //     textAlign: TextAlign.center,
          //   ),
          // ),
        ],
      ),
    );
  }
}