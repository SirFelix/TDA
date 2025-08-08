import 'package:flutter/material.dart';
import 'package:accordion/accordion.dart';
import 'package:tda_app/dropdowns/daq_dropdown.dart';

class ControlPanelAccordion extends StatelessWidget {
  const ControlPanelAccordion({super.key});

  static const headerStyle = TextStyle(color: Color(0xffffffff), fontSize: 16, fontWeight: FontWeight.bold);
  static const contentStyleHeader = TextStyle(color: Color(0xff999999), fontSize: 14, fontWeight: FontWeight.w700);
  static const contentStyle = TextStyle(color: Color.fromARGB(255, 153, 153, 153), fontSize: 14, fontWeight: FontWeight.normal);

  @override
  Widget build(BuildContext context) { // Changed build method return type to Widget
    return Container(
      color: const Color.fromARGB(0, 255, 255, 255),
      width: double.infinity,
      child: Column( // This Column is the main layout container
        children: [
          Container( // Header
            color: const Color.fromARGB(255, 33, 29, 159),
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
                headerBackgroundColor:  Colors.deepOrange,
                headerBackgroundColorOpened:   Color.fromARGB(255, 255, 109, 4),
                // headerBorderColor: Colors.green,
                // headerBorderColorOpened: Colors.red,
                contentBorderColor: Color.fromARGB(255, 255, 109, 4),
                headerBorderWidth: 10,
                contentBorderWidth: 4,
                scaleWhenAnimating: true,
                openAndCloseAnimation: true,
                paddingListTop: 0,
                paddingListHorizontal: 0,
                paddingBetweenClosedSections: 0,
                paddingBetweenOpenSections: 0,
                headerBorderRadius: 0,
                contentBorderRadius: 0,
                children: [
                  AccordionSection(
                    isOpen: true,
                    contentVerticalPadding: 0,
                    headerPadding: const EdgeInsets.symmetric(horizontal: 0),
                    leftIcon: const Icon(Icons.text_fields_rounded, color: Colors.white),
                    header: const Text('DAQ Setup', style: headerStyle),
                    // content: Text('Content 1', style: contentStyle),
                    content: const DaqDropdown(),
                  ),
                  AccordionSection(
                    header: const Text('Header 2', style: headerStyle),
                    content: Text('Content 2', style: contentStyle),
                  ),
                  AccordionSection(
                    header: const Text('Header 3', style: headerStyle),
                    content: Text('Content 3', style: contentStyle),
                  ),
                ],
              ),
            ),
          ),

          // const Spacer(), // Spacer (fills remaining space)
          Container( // Footer
            padding: const EdgeInsets.all(10),
            color: Colors.deepOrange,
            width: double.infinity,
            child: const Text(
              'App Settings',
              style: TextStyle(color: Color.fromARGB(230, 255, 255, 255), fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}