import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/employee_providers.dart';
import 'package:employee_frontend/core/theme/app_theme.dart';

class EmployeeLoginPage extends ConsumerStatefulWidget {
  const EmployeeLoginPage({super.key});

  @override
  ConsumerState<EmployeeLoginPage> createState() => _EmployeeLoginPageState();
}

class _EmployeeLoginPageState extends ConsumerState<EmployeeLoginPage> {
  String _query = '';
  String _department = 'All';

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(employeeAuthProvider);
    final departments = [
      'All',
      ...{
        for (final employee in auth.employees) employee.department,
      }
    ];
    final employees = auth.employees.where((employee) {
      final haystack =
          '${employee.name} ${employee.employeeId} ${employee.department} ${employee.jobTitle}'
              .toLowerCase();
      final matchesQuery =
          _query.isEmpty || haystack.contains(_query.toLowerCase());
      final matchesDepartment =
          _department == 'All' || employee.department == _department;
      return matchesQuery && matchesDepartment;
    }).toList();

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        child: Container(
          decoration: AppTheme.pageBackground(),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1180),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          height: 44,
                          width: 44,
                          decoration: BoxDecoration(
                            gradient: AppTheme.primaryGradient,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Center(
                            child: Text(
                              'PC',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Employee learning access',
                                style: TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF101828),
                                ),
                              ),
                              SizedBox(height: 3),
                              Text(
                                'Select a synced employee for local testing.',
                                style: TextStyle(color: Color(0xFF667085)),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          onPressed: auth.isLoading
                              ? null
                              : () => ref
                                  .read(employeeAuthProvider.notifier)
                                  .fetchEmployees(),
                          icon: const Icon(Icons.refresh),
                          tooltip: 'Refresh employees',
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Material(
                      color: Colors.transparent,
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: AppTheme.cardDecoration(),
                        child: Row(
                          children: [
                            Expanded(
                              child: TextField(
                                onChanged: (value) =>
                                    setState(() => _query = value),
                                decoration: const InputDecoration(
                                  prefixIcon: Icon(Icons.search),
                                  hintText:
                                      'Search by name, employee ID, department, or job title',
                                  border: OutlineInputBorder(),
                                  isDense: true,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            SizedBox(
                              width: 220,
                              child: DropdownButtonFormField<String>(
                                isExpanded: true,
                                value: _department,
                                decoration: const InputDecoration(
                                  labelText: 'Department',
                                  border: OutlineInputBorder(),
                                  isDense: true,
                                ),
                                items: departments
                                    .map((department) => DropdownMenuItem(
                                          value: department,
                                          child: Text(department),
                                        ))
                                    .toList(),
                                onChanged: (value) {
                                  if (value != null) {
                                    setState(() => _department = value);
                                  }
                                },
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (auth.error != null) ...[
                      const SizedBox(height: 14),
                      _LoginNotice(message: auth.error!),
                    ],
                    const SizedBox(height: 18),
                    Expanded(
                      child: auth.isLoading && auth.employees.isEmpty
                          ? const Center(child: CircularProgressIndicator())
                          : employees.isEmpty
                              ? const _EmptyEmployees()
                              : LayoutBuilder(
                                  builder: (context, constraints) {
                                    final columns = constraints.maxWidth >= 1040
                                        ? 3
                                        : constraints.maxWidth >= 680
                                            ? 2
                                            : 1;
                                    final cardHeight =
                                        constraints.maxWidth >= 680
                                            ? 210.0
                                            : 220.0;
                                    return GridView.builder(
                                      itemCount: employees.length,
                                      gridDelegate:
                                          SliverGridDelegateWithFixedCrossAxisCount(
                                        crossAxisCount: columns,
                                        mainAxisExtent: cardHeight,
                                        mainAxisSpacing: 14,
                                        crossAxisSpacing: 14,
                                      ),
                                      itemBuilder: (context, index) =>
                                          _EmployeeCard(
                                        employee: employees[index],
                                        isBusy: auth.isLoading,
                                        onSelect: () => ref
                                            .read(employeeAuthProvider.notifier)
                                            .login(employees[index]),
                                      ),
                                    );
                                  },
                                ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _EmployeeCard extends StatelessWidget {
  final Employee employee;
  final bool isBusy;
  final VoidCallback onSelect;

  const _EmployeeCard({
    required this.employee,
    required this.isBusy,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppTheme.lightGray),
      ),
      child: InkWell(
        onTap: isBusy ? null : onSelect,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    backgroundColor: AppTheme.brandBlue100,
                    child: Text(
                      _initials(employee.name),
                      style: const TextStyle(
                        color: AppTheme.primaryBlue,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          employee.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          employee.employeeId,
                          style: const TextStyle(
                            color: Color(0xFF667085),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _MetaLine(
                  icon: Icons.apartment_outlined, text: employee.department),
              const SizedBox(height: 7),
              _MetaLine(icon: Icons.badge_outlined, text: employee.jobTitle),
              const SizedBox(height: 7),
              _MetaLine(
                icon: Icons.calendar_today_outlined,
                text: 'Joined ${employee.joinDate}',
              ),
              const Spacer(),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  onPressed: isBusy ? null : onSelect,
                  icon: const Icon(Icons.login, size: 18),
                  label: const Text('Open session'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _initials(String name) {
    final parts =
        name.trim().split(RegExp(r'\s+')).where((part) => part.isNotEmpty);
    return parts.take(2).map((part) => part[0]).join().toUpperCase();
  }
}

class _MetaLine extends StatelessWidget {
  final IconData icon;
  final String text;

  const _MetaLine({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: const Color(0xFF667085)),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Color(0xFF344054), fontSize: 13),
          ),
        ),
      ],
    );
  }
}

class _LoginNotice extends StatelessWidget {
  final String message;

  const _LoginNotice({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7E8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFF3D19C)),
      ),
      child: Text(message, style: const TextStyle(color: Color(0xFF704A00))),
    );
  }
}

class _EmptyEmployees extends StatelessWidget {
  const _EmptyEmployees();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'No employees match the current filters.',
        style: TextStyle(color: Color(0xFF667085)),
      ),
    );
  }
}
